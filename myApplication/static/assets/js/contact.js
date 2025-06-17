document.addEventListener('DOMContentLoaded', function() {
    const form = document.querySelector('.php-email-form');
    const loading = document.querySelector('.loading');
    const errorMessage = document.querySelector('.error-message');
    const sentMessage = document.querySelector('.sent-message');

    // Show loading on submit
    form.addEventListener('submit', function() {
        loading.style.display = 'block';
        errorMessage.style.display = 'none';
        sentMessage.style.display = 'none';
    });

    // Show messages if present
    if (sentMessage.innerText.trim()) {
        sentMessage.style.display = 'block';
        loading.style.display = 'none';
    }
    if (errorMessage.innerText.trim()) {
        errorMessage.style.display = 'block';
        loading.style.display = 'none';
    }

    // Scroll to contact section if active
    if (window.location.pathname === '/contact/' || '{{ active_section }}' === 'contact') {
        document.getElementById('contact').scrollIntoView({ behavior: 'smooth' });
    }
});