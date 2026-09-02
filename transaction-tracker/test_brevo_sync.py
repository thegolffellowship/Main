"""Tracker → Brevo member-status sync (email_parser/brevo.py).

Runs entirely offline: requests is monkeypatched with a fake Brevo that
records what the sync would write. Verifies status mapping, chapter
rules, the no-key no-op, batch/fallback behaviour, and the
create-missing dial gate.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class _Resp:
    def __init__(self, status=200, body=None, text=""):
        self.status_code = status
        self._body = body if body is not None else {}
        self.text = text or json.dumps(self._body)
        self.ok = status < 400

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeBrevo:
    def __init__(self, contacts, batch_ok=True):
        self.contacts = contacts          # {email: attrs}
        self.batch_ok = batch_ok
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append(("GET", url, params))
        if url.endswith("/account"):
            return _Resp(200, {"email": "kerry@x", "companyName": "TGF"})
        if url.endswith("/contacts"):
            off = (params or {}).get("offset", 0)
            rows = [{"id": i + 1, "email": e, "attributes": a}
                    for i, (e, a) in enumerate(self.contacts.items())]
            return _Resp(200, {"contacts": rows[off:off + 1000]})
        return _Resp(404, text="nope")

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(("POST", url, json))
        if "/attributes/" in url:
            return _Resp(400, text='{"message":"Attribute already exists"}')
        if url.endswith("/contacts/batch"):
            if not self.batch_ok:
                return _Resp(400, text="Contact does not exist")
            for c in json["contacts"]:
                self.contacts[c["email"]].update(c["attributes"])
            return _Resp(204)
        if url.endswith("/contacts/import"):
            return _Resp(202, {"processId": 7})
        return _Resp(404)

    def put(self, url, json=None, headers=None, timeout=None):
        self.calls.append(("PUT", url, json))
        email = url.rsplit("/", 1)[1].replace("%40", "@")
        if email not in self.contacts:
            return _Resp(404, text="Contact does not exist")
        self.contacts[email].update(json["attributes"])
        return _Resp(204)


TARGETS = {
    "a@x.com": {"status": "active_member", "chapter": "San Antonio"},
    "b@x.com": {"status": "former_member", "chapter": "Austin"},
    "c@x.com": {"status": "prospect", "chapter": ""},
    "d@x.com": {"status": "prospect", "chapter": "Austin"},   # not in Brevo
    "e@x.com": {"status": "active_member", "chapter": "Austin",
                "first_name": "Eve", "last_name": "Ng"},      # not in Brevo
    "e2@x.com": {"status": "active_member", "chapter": "Austin",
                 "importable": False},                        # Eve's 2nd email
    "f@x.com": {"status": "prospect", "chapter": "San Antonio",
                "last_played": "2026-06-14"},                 # recent guest
    "g@x.com": {"status": "former_member", "chapter": "Austin",
                "last_played": "2024-03-02"},                 # stale alumni
}


class BrevoSyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "t.db")
        os.environ["DATABASE_PATH"] = self.db
        os.environ["BREVO_API_KEY"] = "k"
        from email_parser import brevo
        self.brevo = brevo
        brevo._PAUSE = 0

    def _run(self, fake, dry=False, create_missing=False):
        dial = (lambda db, key, db_path: create_missing if (
            create_missing and key == "brevo_sync_create_missing") else None)
        with mock.patch.object(self.brevo, "requests", fake), \
             mock.patch.object(self.brevo, "_dial", dial), \
             mock.patch.object(self.brevo, "tracker_contact_targets",
                               lambda db_path=None: dict(TARGETS)):
            return self.brevo.sync_member_status(db_path=self.db, dry_run=dry)

    def test_no_key_is_noop(self):
        os.environ["BREVO_API_KEY"] = ""
        res = self.brevo.sync_member_status(db_path=self.db)
        self.assertEqual(res["error"], "BREVO_API_KEY not set")

    def test_stamps_only_changed_contacts(self):
        fake = FakeBrevo({"a@x.com": {"TGF_MEMBER_STATUS": "active_member",
                                      "TGF_CHAPTER": "San Antonio"},
                          "b@x.com": {}, "c@x.com": {"TGF_CHAPTER": "Austin"},
                          "z@x.com": {}})
        res = self._run(fake)
        self.assertEqual(res["matched"], 3)
        self.assertEqual(res["to_update"], 2)        # a is already right
        self.assertEqual(res["updated"], 2)
        self.assertEqual(res["missing_in_brevo"], 4)   # d e f g (e2 not importable)
        self.assertEqual(res["created"], 0)          # dial off
        self.assertEqual(fake.contacts["b@x.com"],
                         {"TGF_MEMBER_STATUS": "former_member",
                          "TGF_CHAPTER": "Austin"})
        # blank Tracker chapter never wipes a Brevo chapter
        self.assertEqual(fake.contacts["c@x.com"]["TGF_CHAPTER"], "Austin")
        self.assertEqual(fake.contacts["c@x.com"]["TGF_MEMBER_STATUS"], "prospect")
        self.assertNotIn("TGF_MEMBER_STATUS", fake.contacts["z@x.com"])
        self.assertEqual(res["by_status"],
                         {"active_member": 3, "former_member": 2, "prospect": 3})
        self.assertFalse(res["errors"])

    def test_dry_run_writes_nothing(self):
        fake = FakeBrevo({"b@x.com": {}})
        res = self._run(fake, dry=True)
        self.assertEqual(res["to_update"], 1)
        self.assertEqual(res["updated"], 0)
        self.assertFalse([c for c in fake.calls if c[0] in ("POST", "PUT")])

    def test_batch_rejection_falls_back_per_contact(self):
        fake = FakeBrevo({"b@x.com": {}, "c@x.com": {}}, batch_ok=False)
        res = self._run(fake)
        self.assertEqual(res["updated"], 2)
        self.assertTrue(any(c[0] == "PUT" for c in fake.calls))
        self.assertEqual(fake.contacts["b@x.com"]["TGF_MEMBER_STATUS"],
                         "former_member")

    def test_create_missing_dial_all(self):
        fake = FakeBrevo({"a@x.com": {}})
        res = self._run(fake, create_missing="1")
        imp = [c for c in fake.calls if c[1].endswith("/contacts/import")]
        self.assertEqual(len(imp), 1)
        self.assertEqual(res["created"], 6)          # b c d e f g — never e2
        self.assertEqual(imp[0][2]["listIds"], [3])
        self.assertFalse(imp[0][2]["emptyContactsAttributes"])
        eve = [r for r in imp[0][2]["jsonBody"] if r["email"] == "e@x.com"][0]
        self.assertEqual(eve["attributes"]["FIRSTNAME"], "Eve")
        self.assertEqual(eve["attributes"]["TGF_MEMBER_STATUS"], "active_member")

    def test_create_missing_dial_recent(self):
        fake = FakeBrevo({"a@x.com": {}})
        res = self._run(fake, create_missing="recent")
        imp = [c for c in fake.calls if c[1].endswith("/contacts/import")]
        self.assertEqual(res["create_scope"], "recent")
        self.assertEqual(sorted(r["email"] for r in imp[0][2]["jsonBody"]),
                         ["e@x.com", "f@x.com"])      # active + played ≤12mo
        f = [r for r in imp[0][2]["jsonBody"] if r["email"] == "f@x.com"][0]
        self.assertEqual(f["attributes"]["TGF_LAST_PLAYED"], "2026-06-14")

    def test_last_played_stamp_triggers_update(self):
        fake = FakeBrevo({"g@x.com": {"TGF_MEMBER_STATUS": "former_member",
                                      "TGF_CHAPTER": "Austin"}})
        res = self._run(fake)
        self.assertEqual(res["updated"], 1)
        self.assertEqual(fake.contacts["g@x.com"]["TGF_LAST_PLAYED"], "2024-03-02")

    def test_create_missing_dial_active_only(self):
        fake = FakeBrevo({"a@x.com": {}})
        res = self._run(fake, create_missing="active")
        imp = [c for c in fake.calls if c[1].endswith("/contacts/import")]
        self.assertEqual(res["create_scope"], "active")
        self.assertEqual(res["to_create"], 1)
        self.assertEqual([r["email"] for r in imp[0][2]["jsonBody"]], ["e@x.com"])


if __name__ == "__main__":
    unittest.main()
