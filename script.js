// script.js

// Function to add interactive animations and scroll effects
document.addEventListener('DOMContentLoaded', function() {
    // Add scroll animations
    const sections = document.querySelectorAll('section');
    const options = {
        root: null,
        threshold: 0.1,
        rootMargin: '0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate'); // Add animate class when in view
            } else {
                entry.target.classList.remove('animate'); // Remove animate class when out of view
            }
        });
    }, options);

    sections.forEach(section => {
        observer.observe(section);
    });

    // Add interactive animations on button click
    const buttons = document.querySelectorAll('.animate-button');
    buttons.forEach(button => {
        button.addEventListener('click', function() {
            this.classList.toggle('active'); // Toggle active class for animation
        });
    });
});