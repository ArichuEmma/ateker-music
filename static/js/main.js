// Ateker Music - Main JavaScript

document.addEventListener('DOMContentLoaded', function() {
    // Auto-hide flash messages after 5 seconds
    const flashes = document.querySelectorAll('[class*="bg-red-50"], [class*="bg-green-50"], [class*="bg-blue-50"]');
    flashes.forEach(function(el) {
        if (el.parentElement && el.parentElement.classList.contains('max-w-7xl')) {
            setTimeout(() => {
                el.style.opacity = '0';
                el.style.transition = 'opacity 0.5s';
                setTimeout(() => el.remove(), 500);
            }, 5000);
        }
    });

    // Confirm delete actions
    document.querySelectorAll('form[onsubmit]').forEach(function(form) {
        form.addEventListener('submit', function(e) {
            const confirmMsg = form.getAttribute('onsubmit');
            if (confirmMsg && confirmMsg.includes('confirm')) {
                // Let the inline onsubmit handle it
            }
        });
    });

    // Active nav link highlighting
    const currentPath = window.location.pathname;
    document.querySelectorAll('.km-nav-links a').forEach(function(link) {
        if (link.getAttribute('href') === currentPath) {
            link.classList.add('text-primary-500');
        }
    });
});
