document.addEventListener('DOMContentLoaded', () => {
    // 1. Navigation Menu functionality
    initializeNavigation();
    
    // 2. Tree Identification Tool
    initializeIdentificationTool();
    
    // 3. Resource Downloads tracking
    initializeResourceTracking();
    
    // 4. Newsletter Form
    initializeNewsletterForm();
    
    // 5. Hero CTA button
    initializeHeroCta();
    
    // 6. Accessibility enhancements
    enhanceAccessibility();
});

// Navigation functions
function initializeNavigation() {
    const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
    const mainNavigation = document.querySelector('.main-navigation');
    
    // Mobile hamburger menu toggle
    if (mobileMenuToggle && mainNavigation) {
        mobileMenuToggle.addEventListener('click', () => {
            mainNavigation.classList.toggle('open');
            const isExpanded = mainNavigation.classList.contains('open');
            mobileMenuToggle.setAttribute('aria-expanded', isExpanded);
            if (isExpanded) {
                mobileMenuToggle.textContent = 'Close';
            } else {
                mobileMenuToggle.textContent = 'Menu';
            }
        });
    }
    
    // Smooth scrolling to page sections
    const navLinks = document.querySelectorAll('.main-navigation a, .footer-content a');
    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            const targetId = link.getAttribute('href');
            if (targetId.startsWith('#') && targetId.length > 1) {
                e.preventDefault();
                const targetElement = document.querySelector(targetId);
                if (targetElement) {
                    // Close mobile menu if open
                    if (mainNavigation && mainNavigation.classList.contains('open')) {
                        mainNavigation.classList.remove('open');
                        mobileMenuToggle.setAttribute('aria-expanded', false);
                        mobileMenuToggle.textContent = 'Menu';
                    }
                    
                    // Smooth scroll to target
                    targetElement.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            }
        });
    });
}

// Tree Identification Tool
function initializeIdentificationTool() {
    const idForm = document.querySelector('.id-form');
    const resultsPanel = document.querySelector('.id-results');
    
    // Sample tree database for matching
    const treesDatabase = [
        {
            name: 'White Pine',
            scientificName: 'Pinus strobus',
            leaf: 'needle',
            bark: 'scaly',
            fruit: 'cone',
            image: 'white-pine.jpg',
            description: 'Tall evergreen with soft, bluish-green needles in bundles of five.'
        },
        {
            name: 'Red Oak',
            scientificName: 'Quercus rubra',
            leaf: 'lobed',
            bark: 'furrowed',
            fruit: 'nut',
            image: 'red-oak.jpg',
            description: 'Deciduous tree with pointed leaf lobes and reddish fall color.'
        },
        {
            name: 'White Birch',
            scientificName: 'Betula papyrifera',
            leaf: 'broad',
            bark: 'peeling',
            fruit: 'samara',
            image: 'white-birch.jpg',
            description: 'Known for its distinctive white, paper-like bark that peels in thin sheets.'
        },
        {
            name: 'Sugar Maple',
            scientificName: 'Acer saccharum',
            leaf: 'lobed',
            bark: 'furrowed',
            fruit: 'samara',
            image: 'sugar-maple.jpg',
            description: 'Known for brilliant fall colors and maple syrup production.'
        },
        {
            name: 'Eastern Red Cedar',
            scientificName: 'Juniperus virginiana',
            leaf: 'scale-like',
            bark: 'peeling',
            fruit: 'berry',
            image: 'red-cedar.jpg',
            description: 'Evergreen with scale-like foliage and blue berry-like cones.'
        }
    ];
    
    // Handle form submission
    if (idForm) {
        idForm.addEventListener('submit', (e) => {
            e.preventDefault();
            
            const leafShape = document.getElementById('leaf-shape').value;
            const barkTexture = document.getElementById('bark-texture').value;
            const fruitType = document.getElementById('fruit-type').value;
            
            // Find matches based on user selections
            const matches = treesDatabase.filter(tree => {
                return (!leafShape || tree.leaf === leafShape) &&
                       (!barkTexture || tree.bark === barkTexture) &&
                       (!fruitType || tree.fruit === fruitType);
            });
            
            // Display results
            displayResults(matches);
            
            // Save to local storage
            saveToLocalStorage({leafShape, barkTexture, fruitType});
        });
    }
    
    // Load previous search from local storage
    loadFromLocalStorage();
    
    // Function to display results
    function displayResults(matches) {
        if (!resultsPanel) return;
        
        if (matches.length === 0) {
            resultsPanel.innerHTML = '<p class="no-results">No matches found. Try different characteristics.</p>';
            return;
        }
        
        let resultsHTML = '';
        matches.forEach(tree => {
            resultsHTML += `
                <div class="tree-result">
                    <h4>${tree.name}</h4>
                    <p class="scientific-name">${tree.scientificName}</p>
                    <p>${tree.description}</p>
                </div>
            `;
        });
        
        resultsPanel.innerHTML = resultsHTML;
    }
    
    // Local storage functions for recent searches
    function saveToLocalStorage(searchCriteria) {
        localStorage.setItem('treeSearchCriteria', JSON.stringify(searchCriteria));
    }
    
    function loadFromLocalStorage() {
        try {
            const savedSearch = localStorage.getItem('treeSearchCriteria');
            if (savedSearch) {
                const criteria = JSON.parse(savedSearch);
                
                // Populate form with saved values
                if (criteria.leafShape) 
                    document.getElementById('leaf-shape').value = criteria.leafShape;
                if (criteria.barkTexture) 
                    document.getElementById('bark-texture').value = criteria.barkTexture;
                if (criteria.fruitType) 
                    document.getElementById('fruit-type').value = criteria.fruitType;
            }
        } catch (error) {
            console.error('Error loading saved search:', error);
            // Clear potentially corrupted data
            localStorage.removeItem('treeSearchCriteria');
        }
    }
}

// Resource Downloads tracking
function initializeResourceTracking() {
    const downloadButtons = document.querySelectorAll('.download-button');
    
    downloadButtons.forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            
            const resourceName = button.parentElement.querySelector('h3').textContent;
            
            // Track the download (could connect to analytics in a real implementation)
            console.log(`Resource downloaded: ${resourceName}`);
            
            // Show confirmation message
            const confirmationMessage = document.createElement('div');
            confirmationMessage.className = 'download-confirmation';
            confirmationMessage.setAttribute('role', 'alert');
            confirmationMessage.textContent = `${resourceName} is downloading...`;
            
            // Insert after the button
            button.parentNode.insertBefore(confirmationMessage, button.nextSibling);
            
            // Remove message after 3 seconds
            setTimeout(() => {
                confirmationMessage.remove();
            }, 3000);
            
            // In a real implementation, would initiate actual download here
            // window.location.href = 'path/to/actual/resource.pdf';
        });
    });
}

// Newsletter Form handling
function initializeNewsletterForm() {
    const newsletterForm = document.querySelector('.newsletter-form');
    
    if (newsletterForm) {
        newsletterForm.addEventListener('submit', (e) => {
            e.preventDefault();
            
            const emailInput = document.getElementById('email');
            const email = emailInput.value.trim();
            
            // Basic validation
            if (!validateEmail(email)) {
                showFormError(emailInput, 'Please enter a valid email address');
                return;
            }
            
            // Simulate AJAX submission
            const formRow = newsletterForm.querySelector('.form-row');
            formRow.innerHTML = '<div class="loading-spinner"></div>';
            
            setTimeout(() => {
                // Simulate successful submission
                newsletterForm.innerHTML = `
                    <div class="success-message" role="alert">
                        <h4>Thank you for subscribing!</h4>
                        <p>You'll receive our tree newsletter at ${email}.</p>
                    </div>
                `;
            }, 1500);
        });
    }
    
    // Email validation helper
    function validateEmail(email) {
        const re = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
        return re.test(email);
    }
    
    // Show form error helper
    function showFormError(inputElement, message) {
        // Remove any existing error messages
        const existingError = inputElement.parentElement.querySelector('.error-message');
        if (existingError) existingError.remove();
        
        // Create and add new error message
        const errorElement = document.createElement('div');
        errorElement.className = 'error-message';
        errorElement.textContent = message;
        errorElement.setAttribute('role', 'alert');
        
        // Insert after the input
        inputElement.parentNode.insertBefore(errorElement, inputElement.nextSibling);
        
        // Focus on the input for accessibility
        inputElement.focus();
    }
}

// Hero CTA button functionality
function initializeHeroCta() {
    const ctaButton = document.querySelector('.cta-button');
    
    if (ctaButton) {
        ctaButton.addEventListener('click', () => {
            // Scroll to tree categories section
            const categoriesSection = document.getElementById('categories');
            if (categoriesSection) {
                categoriesSection.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    }
}

// Accessibility enhancements
function enhanceAccessibility() {
    // Add ARIA attributes to interactive elements
    const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
    if (mobileMenuToggle) {
        mobileMenuToggle.setAttribute('aria-controls', 'main-navigation');
        mobileMenuToggle.setAttribute('aria-expanded', 'false');
        mobileMenuToggle.setAttribute('aria-label', 'Toggle navigation menu');
    }
    
    // Ensure all interactive elements are keyboard accessible
    const interactiveElements = document.querySelectorAll('a, button, select, input');
    interactiveElements.forEach(element => {
        // Ensure tabindex is appropriate
        if (element.getAttribute('tabindex') === '-1' && !element.hasAttribute('disabled')) {
            element.setAttribute('tabindex', '0');
        }
        
        // Add keyboard event listeners for non-native interactive elements
        if (element.classList.contains('category-card') || element.classList.contains('resource-item')) {
            element.addEventListener('keydown', (e) => {
                // Activate on Enter or Space key
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    element.click();
                }
            });
        }
    });
    
    // Add skip-to-content functionality
    const skipLink = document.createElement('a');
    skipLink.className = 'skip-to-content';
    skipLink.href = '#main';
    skipLink.textContent = 'Skip to main content';
    document.body.insertBefore(skipLink, document.body.firstChild);
}