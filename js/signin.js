/**
 * The Golf Fellowship - Sign In Page
 * Authentication token handling and form validation
 */

/**
 * AuthTokenManager - Handles JWT token operations
 * Provides secure token storage, validation, and lifecycle management
 */
class AuthTokenManager {
    constructor() {
        this.ACCESS_TOKEN_KEY = 'tgf_access_token';
        this.REFRESH_TOKEN_KEY = 'tgf_refresh_token';
        this.TOKEN_EXPIRY_KEY = 'tgf_token_expiry';
        this.USER_DATA_KEY = 'tgf_user_data';
        this.REMEMBER_ME_KEY = 'tgf_remember_me';
    }

    /**
     * Get the appropriate storage based on remember me preference
     * @returns {Storage} localStorage or sessionStorage
     */
    getStorage() {
        const rememberMe = localStorage.getItem(this.REMEMBER_ME_KEY) === 'true';
        return rememberMe ? localStorage : sessionStorage;
    }

    /**
     * Decode a JWT token payload (base64url decode)
     * @param {string} token - JWT token string
     * @returns {Object|null} Decoded payload or null if invalid
     */
    decodeToken(token) {
        try {
            if (!token || typeof token !== 'string') {
                return null;
            }

            const parts = token.split('.');
            if (parts.length !== 3) {
                console.error('Invalid token format: expected 3 parts');
                return null;
            }

            // Base64url decode the payload (second part)
            const payload = parts[1];
            const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
            const padded = base64 + '=='.slice(0, (4 - base64.length % 4) % 4);
            const decoded = atob(padded);

            return JSON.parse(decoded);
        } catch (error) {
            console.error('Failed to decode token:', error.message);
            return null;
        }
    }

    /**
     * Check if a token is expired
     * @param {string} token - JWT token string
     * @returns {boolean} True if expired or invalid
     */
    isTokenExpired(token) {
        const payload = this.decodeToken(token);

        if (!payload || !payload.exp) {
            return true;
        }

        // exp is in seconds, Date.now() is in milliseconds
        const expiryTime = payload.exp * 1000;
        const currentTime = Date.now();

        // Add a 30-second buffer to account for clock skew
        return currentTime >= (expiryTime - 30000);
    }

    /**
     * Get time until token expires
     * @param {string} token - JWT token string
     * @returns {number} Milliseconds until expiry, or 0 if expired
     */
    getTimeUntilExpiry(token) {
        const payload = this.decodeToken(token);

        if (!payload || !payload.exp) {
            return 0;
        }

        const expiryTime = payload.exp * 1000;
        const timeLeft = expiryTime - Date.now();

        return Math.max(0, timeLeft);
    }

    /**
     * Store authentication tokens
     * @param {Object} authData - Authentication response data
     * @param {string} authData.accessToken - Access token
     * @param {string} authData.refreshToken - Refresh token (optional)
     * @param {Object} authData.user - User data (optional)
     * @param {boolean} rememberMe - Whether to persist in localStorage
     */
    storeTokens(authData, rememberMe = false) {
        // Store remember me preference in localStorage (always)
        localStorage.setItem(this.REMEMBER_ME_KEY, String(rememberMe));

        const storage = this.getStorage();

        // Store access token
        if (authData.accessToken) {
            storage.setItem(this.ACCESS_TOKEN_KEY, authData.accessToken);

            // Store expiry time for quick access
            const payload = this.decodeToken(authData.accessToken);
            if (payload && payload.exp) {
                storage.setItem(this.TOKEN_EXPIRY_KEY, String(payload.exp * 1000));
            }
        }

        // Store refresh token if provided
        if (authData.refreshToken) {
            storage.setItem(this.REFRESH_TOKEN_KEY, authData.refreshToken);
        }

        // Store user data if provided
        if (authData.user) {
            storage.setItem(this.USER_DATA_KEY, JSON.stringify(authData.user));
        }
    }

    /**
     * Get the stored access token
     * @returns {string|null} Access token or null
     */
    getAccessToken() {
        return this.getStorage().getItem(this.ACCESS_TOKEN_KEY);
    }

    /**
     * Get the stored refresh token
     * @returns {string|null} Refresh token or null
     */
    getRefreshToken() {
        return this.getStorage().getItem(this.REFRESH_TOKEN_KEY);
    }

    /**
     * Get stored user data
     * @returns {Object|null} User data or null
     */
    getUserData() {
        try {
            const userData = this.getStorage().getItem(this.USER_DATA_KEY);
            return userData ? JSON.parse(userData) : null;
        } catch {
            return null;
        }
    }

    /**
     * Check if user is authenticated with a valid token
     * @returns {boolean} True if authenticated with valid token
     */
    isAuthenticated() {
        const token = this.getAccessToken();
        return token !== null && !this.isTokenExpired(token);
    }

    /**
     * Clear all stored tokens and user data
     */
    clearTokens() {
        // Clear from both storages to ensure complete logout
        const keys = [
            this.ACCESS_TOKEN_KEY,
            this.REFRESH_TOKEN_KEY,
            this.TOKEN_EXPIRY_KEY,
            this.USER_DATA_KEY
        ];

        keys.forEach(key => {
            localStorage.removeItem(key);
            sessionStorage.removeItem(key);
        });

        // Keep remember me preference in localStorage
    }

    /**
     * Get authorization header value
     * @returns {string|null} Bearer token string or null
     */
    getAuthHeader() {
        const token = this.getAccessToken();
        return token ? `Bearer ${token}` : null;
    }
}

/**
 * AuthService - Handles authentication API interactions
 */
class AuthService {
    constructor(tokenManager) {
        this.tokenManager = tokenManager;
        this.API_BASE_URL = '/api/auth'; // Configure for your backend
        this.refreshPromise = null;
        this.tokenRefreshTimer = null;
    }

    /**
     * Authenticate user with credentials
     * @param {string} email - User email
     * @param {string} password - User password
     * @param {boolean} rememberMe - Persist session
     * @returns {Promise<Object>} Authentication result
     */
    async login(email, password, rememberMe = false) {
        try {
            // Make API request to authenticate
            const response = await this.makeAuthRequest('/login', {
                method: 'POST',
                body: JSON.stringify({ email, password })
            });

            if (!response.success) {
                throw new AuthError(response.message || 'Authentication failed', response.code);
            }

            // Store tokens
            this.tokenManager.storeTokens({
                accessToken: response.accessToken,
                refreshToken: response.refreshToken,
                user: response.user
            }, rememberMe);

            // Set up automatic token refresh
            this.scheduleTokenRefresh();

            return {
                success: true,
                user: response.user
            };
        } catch (error) {
            if (error instanceof AuthError) {
                throw error;
            }
            throw new AuthError('Network error. Please try again.', 'NETWORK_ERROR');
        }
    }

    /**
     * Refresh the access token using refresh token
     * @returns {Promise<boolean>} True if refresh successful
     */
    async refreshAccessToken() {
        // Prevent multiple simultaneous refresh attempts
        if (this.refreshPromise) {
            return this.refreshPromise;
        }

        const refreshToken = this.tokenManager.getRefreshToken();

        if (!refreshToken) {
            this.logout();
            return false;
        }

        this.refreshPromise = (async () => {
            try {
                const response = await this.makeAuthRequest('/refresh', {
                    method: 'POST',
                    body: JSON.stringify({ refreshToken })
                });

                if (!response.success || !response.accessToken) {
                    throw new Error('Token refresh failed');
                }

                // Get current remember me preference
                const rememberMe = localStorage.getItem(this.tokenManager.REMEMBER_ME_KEY) === 'true';

                // Store new tokens
                this.tokenManager.storeTokens({
                    accessToken: response.accessToken,
                    refreshToken: response.refreshToken || refreshToken
                }, rememberMe);

                // Schedule next refresh
                this.scheduleTokenRefresh();

                return true;
            } catch (error) {
                console.error('Token refresh failed:', error);
                this.logout();
                return false;
            } finally {
                this.refreshPromise = null;
            }
        })();

        return this.refreshPromise;
    }

    /**
     * Schedule automatic token refresh before expiry
     */
    scheduleTokenRefresh() {
        // Clear existing timer
        if (this.tokenRefreshTimer) {
            clearTimeout(this.tokenRefreshTimer);
        }

        const token = this.tokenManager.getAccessToken();
        if (!token) return;

        const timeUntilExpiry = this.tokenManager.getTimeUntilExpiry(token);

        // Refresh 2 minutes before expiry, or immediately if less than 2 minutes left
        const refreshIn = Math.max(0, timeUntilExpiry - 120000);

        if (refreshIn > 0) {
            this.tokenRefreshTimer = setTimeout(() => {
                this.refreshAccessToken();
            }, refreshIn);
        } else if (timeUntilExpiry > 0) {
            // Token expires soon, refresh immediately
            this.refreshAccessToken();
        }
    }

    /**
     * Log out user and clear tokens
     */
    logout() {
        // Clear refresh timer
        if (this.tokenRefreshTimer) {
            clearTimeout(this.tokenRefreshTimer);
            this.tokenRefreshTimer = null;
        }

        // Clear stored tokens
        this.tokenManager.clearTokens();

        // Dispatch logout event for UI updates
        window.dispatchEvent(new CustomEvent('auth:logout'));
    }

    /**
     * Check current authentication status
     * @returns {Object} Auth status with user data if authenticated
     */
    getAuthStatus() {
        const isAuthenticated = this.tokenManager.isAuthenticated();

        return {
            isAuthenticated,
            user: isAuthenticated ? this.tokenManager.getUserData() : null,
            expiresIn: isAuthenticated
                ? this.tokenManager.getTimeUntilExpiry(this.tokenManager.getAccessToken())
                : 0
        };
    }

    /**
     * Make authenticated API request
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Fetch options
     * @returns {Promise<Object>} Response data
     */
    async makeAuthRequest(endpoint, options = {}) {
        const url = `${this.API_BASE_URL}${endpoint}`;

        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        // Add auth header if we have a token (except for login/refresh)
        const authHeader = this.tokenManager.getAuthHeader();
        if (authHeader && !endpoint.includes('/login') && !endpoint.includes('/refresh')) {
            headers['Authorization'] = authHeader;
        }

        const response = await fetch(url, {
            ...options,
            headers,
            credentials: 'include' // Include cookies for CSRF protection
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new AuthError(
                errorData.message || `Request failed with status ${response.status}`,
                errorData.code || 'REQUEST_FAILED'
            );
        }

        return response.json();
    }
}

/**
 * Custom error class for authentication errors
 */
class AuthError extends Error {
    constructor(message, code) {
        super(message);
        this.name = 'AuthError';
        this.code = code;
    }
}

/**
 * Mock API for development/demo purposes
 * Replace with real API calls in production
 */
class MockAuthAPI {
    static DEMO_USERS = {
        'member@golfclub.com': {
            password: 'password123',
            user: {
                id: '1',
                email: 'member@golfclub.com',
                name: 'John Smith',
                membershipType: 'Premium',
                handicap: 12
            }
        },
        'demo@example.com': {
            password: 'demo1234',
            user: {
                id: '2',
                email: 'demo@example.com',
                name: 'Demo User',
                membershipType: 'Standard',
                handicap: 18
            }
        }
    };

    /**
     * Generate a mock JWT token
     */
    static generateMockToken(user, expiresInMinutes = 15) {
        const header = { alg: 'HS256', typ: 'JWT' };
        const now = Math.floor(Date.now() / 1000);
        const payload = {
            sub: user.id,
            email: user.email,
            name: user.name,
            iat: now,
            exp: now + (expiresInMinutes * 60)
        };

        // Base64url encode
        const encode = (obj) => {
            const json = JSON.stringify(obj);
            const base64 = btoa(json);
            return base64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
        };

        // Create mock token (signature is fake, for demo only)
        return `${encode(header)}.${encode(payload)}.mock_signature_${Date.now()}`;
    }

    /**
     * Simulate login API call
     */
    static async login(email, password) {
        // Simulate network delay
        await new Promise(resolve => setTimeout(resolve, 1000));

        const userEntry = this.DEMO_USERS[email.toLowerCase()];

        if (!userEntry) {
            return {
                success: false,
                message: 'No account found with this email address',
                code: 'USER_NOT_FOUND'
            };
        }

        if (userEntry.password !== password) {
            return {
                success: false,
                message: 'Incorrect password. Please try again.',
                code: 'INVALID_PASSWORD'
            };
        }

        return {
            success: true,
            accessToken: this.generateMockToken(userEntry.user, 15), // 15 min expiry
            refreshToken: this.generateMockToken(userEntry.user, 60 * 24 * 7), // 7 day expiry
            user: userEntry.user
        };
    }

    /**
     * Simulate token refresh API call
     */
    static async refresh(refreshToken) {
        await new Promise(resolve => setTimeout(resolve, 500));

        // In a real implementation, validate the refresh token
        // For demo, just generate a new access token
        const tokenManager = new AuthTokenManager();
        const payload = tokenManager.decodeToken(refreshToken);

        if (!payload || !payload.email) {
            return {
                success: false,
                message: 'Invalid refresh token',
                code: 'INVALID_REFRESH_TOKEN'
            };
        }

        return {
            success: true,
            accessToken: this.generateMockToken({
                id: payload.sub,
                email: payload.email,
                name: payload.name
            }, 15)
        };
    }
}

// ============================================================
// Form Handling and UI
// ============================================================

document.addEventListener('DOMContentLoaded', function() {
    // Initialize auth services
    const tokenManager = new AuthTokenManager();
    const authService = new AuthService(tokenManager);

    // Check if already authenticated
    if (tokenManager.isAuthenticated()) {
        const user = tokenManager.getUserData();
        showSuccess(user?.name || 'Member');
        redirectToDashboard();
        return;
    }

    // Get form elements
    const form = document.getElementById('signin-form');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const emailError = document.getElementById('email-error');
    const passwordError = document.getElementById('password-error');
    const togglePasswordBtn = document.querySelector('.toggle-password');
    const btnText = document.querySelector('.btn-text');
    const btnLoader = document.querySelector('.btn-loader');
    const submitBtn = document.querySelector('.btn-signin');

    // Email validation regex
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

    /**
     * Validate email field
     */
    function validateEmail() {
        const email = emailInput.value.trim();

        if (!email) {
            showError(emailInput, emailError, 'Email address is required');
            return false;
        }

        if (!emailRegex.test(email)) {
            showError(emailInput, emailError, 'Please enter a valid email address');
            return false;
        }

        clearError(emailInput, emailError);
        return true;
    }

    /**
     * Validate password field
     */
    function validatePassword() {
        const password = passwordInput.value;

        if (!password) {
            showError(passwordInput, passwordError, 'Password is required');
            return false;
        }

        if (password.length < 8) {
            showError(passwordInput, passwordError, 'Password must be at least 8 characters');
            return false;
        }

        clearError(passwordInput, passwordError);
        return true;
    }

    /**
     * Show error message for a field
     */
    function showError(input, errorElement, message) {
        input.classList.add('error');
        errorElement.textContent = message;
    }

    /**
     * Clear error message for a field
     */
    function clearError(input, errorElement) {
        input.classList.remove('error');
        errorElement.textContent = '';
    }

    /**
     * Toggle password visibility
     */
    function togglePasswordVisibility() {
        const eyeIcon = togglePasswordBtn.querySelector('.eye-icon');
        const eyeOffIcon = togglePasswordBtn.querySelector('.eye-off-icon');

        if (passwordInput.type === 'password') {
            passwordInput.type = 'text';
            eyeIcon.classList.add('hidden');
            eyeOffIcon.classList.remove('hidden');
        } else {
            passwordInput.type = 'password';
            eyeIcon.classList.remove('hidden');
            eyeOffIcon.classList.add('hidden');
        }
    }

    /**
     * Set loading state on submit button
     */
    function setLoading(isLoading) {
        if (isLoading) {
            btnText.classList.add('hidden');
            btnLoader.classList.remove('hidden');
            submitBtn.disabled = true;
        } else {
            btnText.classList.remove('hidden');
            btnLoader.classList.add('hidden');
            submitBtn.disabled = false;
        }
    }

    /**
     * Show success state
     */
    function showSuccess(userName = 'Member') {
        const card = document.querySelector('.signin-card');
        card.innerHTML = `
            <div class="success-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
            </div>
            <h2 style="margin-bottom: 8px; color: #1a1a1a;">Welcome Back, ${escapeHtml(userName)}!</h2>
            <p style="color: #666;">You have successfully signed in.</p>
            <p style="color: #666; margin-top: 16px;">Redirecting to your dashboard...</p>
        `;
        card.classList.add('success');
    }

    /**
     * Show authentication error
     */
    function showAuthError(error) {
        let field = emailInput;
        let errorEl = emailError;

        // Determine which field to show error on based on error code
        if (error.code === 'INVALID_PASSWORD') {
            field = passwordInput;
            errorEl = passwordError;
        }

        showError(field, errorEl, error.message);
    }

    /**
     * Escape HTML to prevent XSS
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * Redirect to dashboard after successful login
     */
    function redirectToDashboard() {
        setTimeout(() => {
            // In production, redirect to actual dashboard
            window.location.href = '/dashboard';
        }, 2000);
    }

    /**
     * Handle form submission
     */
    async function handleSubmit(e) {
        e.preventDefault();

        // Validate all fields
        const isEmailValid = validateEmail();
        const isPasswordValid = validatePassword();

        if (!isEmailValid || !isPasswordValid) {
            return;
        }

        // Show loading state
        setLoading(true);

        try {
            const email = emailInput.value.trim();
            const password = passwordInput.value;
            const rememberMe = document.getElementById('remember').checked;

            // Use mock API for demo (replace with real API in production)
            const response = await MockAuthAPI.login(email, password);

            if (!response.success) {
                throw new AuthError(response.message, response.code);
            }

            // Store tokens using token manager
            tokenManager.storeTokens({
                accessToken: response.accessToken,
                refreshToken: response.refreshToken,
                user: response.user
            }, rememberMe);

            // Schedule token refresh
            authService.scheduleTokenRefresh();

            // Clear password from memory
            passwordInput.value = '';

            // Show success state
            showSuccess(response.user?.name);

            // Redirect to dashboard
            redirectToDashboard();

        } catch (error) {
            console.error('Sign in error:', error);

            if (error instanceof AuthError) {
                showAuthError(error);
            } else {
                showError(emailInput, emailError, 'An error occurred. Please try again.');
            }

            setLoading(false);
        }
    }

    // Event Listeners
    form.addEventListener('submit', handleSubmit);

    // Real-time validation on blur
    emailInput.addEventListener('blur', validateEmail);
    passwordInput.addEventListener('blur', validatePassword);

    // Clear errors on input
    emailInput.addEventListener('input', function() {
        if (emailInput.classList.contains('error')) {
            clearError(emailInput, emailError);
        }
    });

    passwordInput.addEventListener('input', function() {
        if (passwordInput.classList.contains('error')) {
            clearError(passwordInput, passwordError);
        }
    });

    // Toggle password visibility
    togglePasswordBtn.addEventListener('click', togglePasswordVisibility);

    // Handle Enter key in password field
    passwordInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            form.dispatchEvent(new Event('submit'));
        }
    });

    // Listen for logout events
    window.addEventListener('auth:logout', function() {
        // Reload page to show login form
        window.location.reload();
    });
});

// Export for use in other modules (if using ES modules)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { AuthTokenManager, AuthService, AuthError };
}
