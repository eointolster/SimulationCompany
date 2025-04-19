document.addEventListener('DOMContentLoaded', () => {
    // Theme toggle functionality
    const themeToggle = document.querySelector('.theme-toggle button');
    themeToggle.addEventListener('click', () => {
        document.body.classList.toggle('dark-mode');
        themeToggle.innerHTML = document.body.classList.contains('dark-mode') ? '☀️' : '🌙';
    });

    // Widget Carousel functionality
    const carousel = document.querySelector('.widget-carousel');
    const prevBtn = document.querySelector('.carousel-controls .prev-btn');
    const nextBtn = document.querySelector('.carousel-controls .next-btn');
    let currentSlide = 0;
    const slides = document.querySelectorAll('.carousel-item');
    const totalSlides = slides.length;

    function updateCarousel() {
        const slideWidth = slides[0].clientWidth;
        carousel.style.transform = `translateX(-${currentSlide * slideWidth}px)`;
        
        // Update button states
        prevBtn.disabled = currentSlide === 0;
        nextBtn.disabled = currentSlide === totalSlides - 1;
    }

    prevBtn.addEventListener('click', () => {
        if (currentSlide > 0) {
            currentSlide--;
            updateCarousel();
        }
    });

    nextBtn.addEventListener('click', () => {
        if (currentSlide < totalSlides - 1) {
            currentSlide++;
            updateCarousel();
        }
    });

    // Initialize carousel positioning
    updateCarousel();
    
    // Responsive carousel update
    window.addEventListener('resize', updateCarousel);

    // Gallery view toggle
    const gridViewBtn = document.querySelector('.grid-view');
    const listViewBtn = document.querySelector('.list-view');
    const galleryGrid = document.querySelector('.gallery-grid');

    gridViewBtn.addEventListener('click', () => {
        galleryGrid.classList.remove('list-layout');
        galleryGrid.classList.add('grid-layout');
        gridViewBtn.classList.add('active');
        listViewBtn.classList.remove('active');
    });

    listViewBtn.addEventListener('click', () => {
        galleryGrid.classList.remove('grid-layout');
        galleryGrid.classList.add('list-layout');
        listViewBtn.classList.add('active');
        gridViewBtn.classList.remove('active');
    });

    // Search and filter functionality
    const searchInput = document.querySelector('.search-filter input[type="search"]');
    const categoryFilter = document.querySelector('select[aria-label="Filter by category"]');
    const difficultyFilter = document.querySelector('select[aria-label="Filter by difficulty"]');
    const widgetCards = document.querySelectorAll('.widget-card');

    function filterGallery() {
        const searchTerm = searchInput.value.toLowerCase();
        const categoryValue = categoryFilter.value;
        const difficultyValue = difficultyFilter.value;

        widgetCards.forEach(card => {
            const title = card.querySelector('h3').textContent.toLowerCase();
            const description = card.querySelector('p').textContent.toLowerCase();
            const difficulty = card.querySelector('.difficulty').textContent.toLowerCase();
            
            // Extract widget category (in a real implementation, you'd have actual data attributes)
            const category = card.dataset.category || ''; // Placeholder, would need actual data

            const matchesSearch = title.includes(searchTerm) || description.includes(searchTerm);
            const matchesCategory = categoryValue === '' || category === categoryValue;
            const matchesDifficulty = difficultyValue === '' || difficulty === difficultyValue;

            if (matchesSearch && matchesCategory && matchesDifficulty) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });
    }

    searchInput.addEventListener('input', filterGallery);
    categoryFilter.addEventListener('change', filterGallery);
    difficultyFilter.addEventListener('change', filterGallery);

    // Pagination functionality
    const pageLinks = document.querySelectorAll('.pagination .page-numbers a');
    const prevPageBtn = document.querySelector('.pagination .prev-page');
    const nextPageBtn = document.querySelector('.pagination .next-page');

    pageLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            pageLinks.forEach(l => l.classList.remove('active'));
            link.classList.add('active');
            
            // In a real implementation, this would load the next page of content
            // For now we'll just update the button states
            const currentPage = parseInt(link.textContent);
            prevPageBtn.disabled = currentPage === 1;
            nextPageBtn.disabled = currentPage === 8; // Assuming 8 is the last page
        });
    });

    prevPageBtn.addEventListener('click', () => {
        const activePage = document.querySelector('.pagination .page-numbers a.active');
        const currentPage = parseInt(activePage.textContent);
        if (currentPage > 1) {
            // Find previous page link and trigger its click event
            const prevPageLink = document.querySelector(`.pagination .page-numbers a:nth-child(${currentPage - 1})`);
            if (prevPageLink) prevPageLink.click();
        }
    });

    nextPageBtn.addEventListener('click', () => {
        const activePage = document.querySelector('.pagination .page-numbers a.active');
        const currentPage = parseInt(activePage.textContent);
        if (currentPage < 8) { // Assuming 8 is the last page
            // Find next page link and trigger its click event
            const nextPageLink = document.querySelector(`.pagination .page-numbers a:nth-child(${currentPage + 1})`);
            if (nextPageLink) nextPageLink.click();
        }
    });

    // Widget customization controls
    const demoButton = document.querySelector('.demo-button.push-3d');
    const buttonTextInput = document.getElementById('button-text');
    const buttonColorInput = document.getElementById('button-color');
    const buttonRadiusInput = document.getElementById('button-radius');
    const shadowDepthInput = document.getElementById('shadow-depth');
    const codeDisplay = document.querySelector('.code-content pre code');

    // Update widget demo based on customization controls
    function updateWidgetDemo() {
        if (!demoButton) return; // Guard clause if on a different page
        
        const buttonText = buttonTextInput.value;
        const buttonColor = buttonColorInput.value;
        const buttonRadius = buttonRadiusInput.value + 'px';
        const shadowDepth = shadowDepthInput.value + 'px';
        
        demoButton.textContent = buttonText;
        demoButton.style.backgroundColor = buttonColor;
        demoButton.style.borderRadius = buttonRadius;
        demoButton.style.boxShadow = `0 ${shadowDepth} 0 0 rgba(0,0,0,0.3)`;
        
        // Update code preview based on customization
        codeDisplay.textContent = `<button class="push-3d" style="background-color: ${buttonColor}; border-radius: ${buttonRadius}; box-shadow: 0 ${shadowDepth} 0 0 rgba(0,0,0,0.3);">${buttonText}</button>`;
    }

    if (buttonTextInput) buttonTextInput.addEventListener('input', updateWidgetDemo);
    if (buttonColorInput) buttonColorInput.addEventListener('input', updateWidgetDemo);
    if (buttonRadiusInput) buttonRadiusInput.addEventListener('input', updateWidgetDemo);
    if (shadowDepthInput) shadowDepthInput.addEventListener('input', updateWidgetDemo);

    // Code tabs functionality
    const codeTabs = document.querySelectorAll('.code-tabs .tab');
    
    codeTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            codeTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // In a real implementation, this would show different code snippets
            // For now, let's simulate showing different code
            const codeType = tab.textContent.trim();
            switch(codeType) {
                case 'HTML':
                    codeDisplay.textContent = `<button class="push-3d">${buttonTextInput ? buttonTextInput.value : 'Click Me!'}</button>`;
                    break;
                case 'CSS':
                    codeDisplay.textContent = `.push-3d {
  background-color: ${buttonColorInput ? buttonColorInput.value : '#4a7dff'};
  border: none;
  border-radius: ${buttonRadiusInput ? buttonRadiusInput.value : '5'}px;
  color: white;
  padding: 12px 24px;
  box-shadow: 0 ${shadowDepthInput ? shadowDepthInput.value : '5'}px 0 0 rgba(0,0,0,0.3);
  transition: transform 0.1s, box-shadow 0.1s;
}

.push-3d:hover {
  transform: translateY(2px);
  box-shadow: 0 ${Math.max(0, (shadowDepthInput ? shadowDepthInput.value : 5) - 2)}px 0 0 rgba(0,0,0,0.3);
}

.push-3d:active {
  transform: translateY(${shadowDepthInput ? shadowDepthInput.value : '5'}px);
  box-shadow: 0 0 0 0 rgba(0,0,0,0.3);
}`;
                    break;
                case 'JavaScript':
                    codeDisplay.textContent = `// Optional JavaScript for button interaction effects
document.querySelectorAll('.push-3d').forEach(button => {
  button.addEventListener('mousedown', () => {
    button.style.transform = 'translateY(${shadowDepthInput ? shadowDepthInput.value : '5'}px)';
    button.style.boxShadow = '0 0 0 0 rgba(0,0,0,0.3)';
  });
  
  window.addEventListener('mouseup', () => {
    button.style.transform = '';
    button.style.boxShadow = '';
  });
});`;
                    break;
            }
        });
    });

    // Copy code button
    const copyCodeBtn = document.querySelector('.copy-code-btn');
    if (copyCodeBtn) {
        copyCodeBtn.addEventListener('click', () => {
            const codeToCopy = codeDisplay.textContent;
            navigator.clipboard.writeText(codeToCopy)
                .then(() => {
                    const originalText = copyCodeBtn.textContent;
                    copyCodeBtn.textContent = 'Copied!';
                    setTimeout(() => {
                        copyCodeBtn.textContent = originalText;
                    }, 2000);
                })
                .catch(err => {
                    console.error('Failed to copy code: ', err);
                });
        });
    }

    // Favorite button functionality
    const favoriteBtn = document.querySelector('.favorite-btn');
    if (favoriteBtn) {
        favoriteBtn.addEventListener('click', () => {
            favoriteBtn.classList.toggle('active');
            favoriteBtn.innerHTML = favoriteBtn.classList.contains('active') ? '♥' : '♡';
        });
    }

    // Share button functionality
    const shareBtn = document.querySelector('.share-btn');
    if (shareBtn) {
        shareBtn.addEventListener('click', () => {
            if (navigator.share) {
                navigator.share({
                    title: document.querySelector('.widget-header h2').textContent,
                    text: 'Check out this awesome JavaScript widget!',
                    url: window.location.href
                })
                .catch(err => {
                    console.error('Share failed:', err);
                });
            } else {
                // Fallback - show a share dialog or copy link to clipboard
                navigator.clipboard.writeText(window.location.href)
                    .then(() => {
                        alert('Link copied to clipboard! Share it with your friends.');
                    })
                    .catch(err => {
                        console.error('Failed to copy link: ', err);
                    });
            }
        });
    }

    // Framework tabs functionality
    const frameworkTabs = document.querySelectorAll('.framework-tab');
    const frameworkContent = document.querySelector('.framework-content');
    
    frameworkTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            frameworkTabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // Update content based on selected framework
            const framework = tab.textContent.trim();
            const h4 = frameworkContent.querySelector('h4');
            if (h4) h4.textContent = `Integrating ButtonCraft with ${framework}`;
            
            // In a real implementation, this would show different content for each framework
            // For now, we'll just update the heading
        });
    });

    // Newsletter form submission
    const newsletterForm = document.querySelector('.newsletter-form');
    if (newsletterForm) {
        newsletterForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const emailInput = newsletterForm.querySelector('input[type="email"]');
            const email = emailInput.value;
            
            // In a real implementation, this would send the data to a server
            // For now, just show a success message
            const formContainer = newsletterForm.parentElement;
            formContainer.innerHTML = `
                <div class="success-message">
                    <h3>Thank you for subscribing!</h3>
                    <p>We've sent a confirmation email to <strong>${email}</strong>.</p>
                </div>
            `;
        });
    }

    // Interactive hero button demo
    const heroButton = document.querySelector('.glow-button');
    if (heroButton) {
        // Create a simple interactive effect for the hero button demo
        heroButton.addEventListener('mouseover', () => {
            heroButton.style.boxShadow = '0 0 15px 5px rgba(74, 125, 255, 0.6)';
        });
        
        heroButton.addEventListener('mouseout', () => {
            heroButton.style.boxShadow = '0 0 5px 2px rgba(74, 125, 255, 0.4)';
        });
        
        heroButton.addEventListener('click', () => {
            heroButton.classList.add('pulse');
            setTimeout(() => {
                heroButton.classList.remove('pulse');
            }, 500);
        });
    }

    // Create some sample widget demo functionality
    const demoWidgets = document.querySelectorAll('.widget-demo');
    demoWidgets.forEach((demo, index) => {
        // Only create demos if they're empty
        if (demo.children.length === 0) {
            switch(index) {
                case 0: // Neon Glow Buttons
                    demo.innerHTML = `<button class="neon-button">Neon Button</button>`;
                    const neonButton = demo.querySelector('.neon-button');
                    if (neonButton) {
                        neonButton.style.backgroundColor = 'transparent';
                        neonButton.style.border = '2px solid #f09';
                        neonButton.style.color = '#f09';
                        neonButton.style.padding = '10px 20px';
                        neonButton.style.borderRadius = '5px';
                        neonButton.style.position = 'relative';
                        neonButton.style.overflow = 'hidden';
                        neonButton.style.transition = 'all 0.3s';
                        
                        neonButton.addEventListener('mouseover', () => {
                            neonButton.style.boxShadow = '0 0 10px #f09, 0 0 20px #f09, 0 0 30px #f09';
                            neonButton.style.textShadow = '0 0 5px #f09';
                        });
                        
                        neonButton.addEventListener('mouseout', () => {
                            neonButton.style.boxShadow = 'none';
                            neonButton.style.textShadow = 'none';
                        });
                    }
                    break;
                case 1: // Toggle Switches
                    demo.innerHTML = `<label class="toggle-switch"><input type="checkbox"><span class="slider"></span></label>`;
                    const toggleSwitch = demo.querySelector('.toggle-switch');
                    const slider = demo.querySelector('.slider');
                    if (toggleSwitch && slider) {
                        toggleSwitch.style.position = 'relative';
                        toggleSwitch.style.display = 'inline-block';
                        toggleSwitch.style.width = '60px';
                        toggleSwitch.style.height = '34px';
                        
                        const input = toggleSwitch.querySelector('input');
                        input.style.opacity = '0';
                        input.style.width = '0';
                        input.style.height = '0';
                        
                        slider.style.position = 'absolute';
                        slider.style.cursor = 'pointer';
                        slider.style.top = '0';
                        slider.style.left = '0';
                        slider.style.right = '0';
                        slider.style.bottom = '0';
                        slider.style.backgroundColor = '#ccc';
                        slider.style.borderRadius = '34px';
                        slider.style.transition = '.4s';
                        
                        slider.insertAdjacentHTML('beforeend', '<span class="slider-knob"></span>');
                        const knob = slider.querySelector('.slider-knob');
                        knob.style.position = 'absolute';
                        knob.style.content = '""';
                        knob.style.height = '26px';
                        knob.style.width = '26px';
                        knob.style.left = '4px';
                        knob.style.bottom = '4px';
                        knob.style.backgroundColor = 'white';
                        knob.style.borderRadius = '50%';
                        knob.style.transition = '.4s';
                        
                        input.addEventListener('change', () => {
                            if (input.checked) {
                                slider.style.backgroundColor = '#2196F3';
                                knob.style.transform = 'translateX(26px)';
                            } else {
                                slider.style.backgroundColor = '#ccc';
                                knob.style.transform = 'translateX(0)';
                            }
                        });
                    }
                    break;
                case 2: // Animated Dropdown Menus
                    demo.innerHTML = `
                        <div class="dropdown">
                            <button class="dropdown-toggle">Dropdown Menu</button>
                            <div class="dropdown-menu">
                                <a href="#">Option 1</a>
                                <a href="#">Option 2</a>
                                <a href="#">Option 3</a>
                            </div>
                        </div>
                    `;
                    const dropdown = demo.querySelector('.dropdown');
                    const dropdownToggle = demo.querySelector('.dropdown-toggle');
                    const dropdownMenu = demo.querySelector('.dropdown-menu');
                    
                    if (dropdown && dropdownToggle && dropdownMenu) {
                        dropdown.style.position = 'relative';
                        dropdown.style.display = 'inline-block';
                        
                        dropdownToggle.style.backgroundColor = '#4a7dff';
                        dropdownToggle.style.color = 'white';
                        dropdownToggle.style.padding = '10px 15px';
                        dropdownToggle.style.border = 'none';
                        dropdownToggle.style.cursor = 'pointer';
                        dropdownToggle.style.borderRadius = '4px';
                        
                        dropdownMenu.style.display = 'none';
                        dropdownMenu.style.position = 'absolute';
                        dropdownMenu.style.backgroundColor = '#f9f9f9';
                        dropdownMenu.style.minWidth = '160px';
                        dropdownMenu.style.boxShadow = '0px 8px 16px 0px rgba(0,0,0,0.2)';
                        dropdownMenu.style.zIndex = '1';
                        dropdownMenu.style.borderRadius = '4px';
                        dropdownMenu.style.overflow = 'hidden';
                        dropdownMenu.style.transition = 'all 0.3s ease';
                        dropdownMenu.style.opacity = '0';
                        dropdownMenu.style.transform = 'translateY(-10px)';
                        
                        const links = dropdownMenu.querySelectorAll('a');
                        links.forEach(link => {
                            link.style.color = 'black';
                            link.style.padding = '12px 16px';
                            link.style.textDecoration = 'none';
                            link.style.display = 'block';
                            link.style.transition = 'background-color 0.2s';
                            
                            link.addEventListener('mouseover', () => {
                                link.style.backgroundColor = '#f1f1f1';
                            });
                            
                            link.addEventListener('mouseout', () => {
                                link.style.backgroundColor = 'transparent';
                            });
                        });
                        
                        dropdownToggle.addEventListener('click', (e) => {
                            e.stopPropagation();
                            const isOpen = dropdownMenu.style.display === 'block';
                            
                            if (isOpen) {
                                dropdownMenu.style.opacity = '0';
                                dropdownMenu.style.transform = 'translateY(-10px)';
                                setTimeout(() => {
                                    dropdownMenu.style.display = 'none';
                                }, 300);
                            } else {
                                dropdownMenu.style.display = 'block';
                                setTimeout(() => {
                                    dropdownMenu.style.opacity = '1';
                                    dropdownMenu.style.transform = 'translateY(0)';
                                }, 10);
                            }
                        });
                        
                        // Close the dropdown when clicking elsewhere
                        document.addEventListener('click', () => {
                            if (dropdownMenu.style.display === 'block') {
                                dropdownMenu.style.opacity = '0';
                                dropdownMenu.style.transform = 'translateY(-10px)';
                                setTimeout(() => {
                                    dropdownMenu.style.display = 'none';
                                }, 300);
                            }
                        });
                    }
                    break;
            }
        }
    });
});