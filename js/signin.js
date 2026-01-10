/**
 * The Golf Fellowship - Sign In Page
 * Form validation and interaction handling
 */

document.addEventListener('DOMContentLoaded', function() {
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
    function showSuccess() {
        const card = document.querySelector('.signin-card');
        card.innerHTML = `
            <div class="success-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
            </div>
            <h2 style="margin-bottom: 8px; color: #1a1a1a;">Welcome Back!</h2>
            <p style="color: #666;">You have successfully signed in.</p>
            <p style="color: #666; margin-top: 16px;">Redirecting to your dashboard...</p>
        `;
        card.classList.add('success');
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
            // Simulate API call
            await new Promise(resolve => setTimeout(resolve, 1500));

            // Get form data
            const formData = {
                email: emailInput.value.trim(),
                password: passwordInput.value,
                remember: document.getElementById('remember').checked
            };

            // Log for demo purposes (remove in production)
            console.log('Sign in attempt:', { email: formData.email, remember: formData.remember });

            // Show success state
            showSuccess();

            // In a real application, you would:
            // 1. Send credentials to your authentication API
            // 2. Store the returned token/session
            // 3. Redirect to the dashboard or protected page

        } catch (error) {
            console.error('Sign in error:', error);
            showError(emailInput, emailError, 'An error occurred. Please try again.');
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
});
