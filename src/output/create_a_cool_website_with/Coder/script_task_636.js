// Main JavaScript for Monkey Magic website
document.addEventListener('DOMContentLoaded', function() {
  // ------ Navigation and General Interactions ------
  initStickyHeader();
  initSmoothScrolling();
  initCustomCursor();
  initQuickFactsTicker();
  
  // ------ Interactive Species Gallery ------
  initSpeciesFilter();
  initSpeciesCardInteraction();
  initLoadMoreSpecies();
  
  // ------ Hero Section Animations ------
  animateHeroSection();
  
  // ------ Learning Zone Interactions ------
  initLearningModules();
  initEducatorResources();
  
  // ------ Habitat Explorer ------
  initHabitatExplorer();
  initSoundControls();
  
  // ------ Conservation Section ------
  initConservationInteractions();
  
  // ------ Design Section ------
  initColorPaletteInteraction();
  initArtworkGallery();
  initDesignChallengeForm();
  
  // ------ Footer Interactions ------
  initSubscriptionForm();
  
  // ------ Accessibility Features ------
  initAccessibilityFeatures();
  
  // ------ Theme Customizer ------
  initThemeCustomizer();
});

// ------ Header and Navigation Functions ------
function initStickyHeader() {
  const header = document.getElementById('main-header');
  let lastScrollTop = 0;
  
  window.addEventListener('scroll', () => {
    const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
    
    if (scrollTop > lastScrollTop) {
      // Scrolling down
      header.classList.add('header-hidden');
    } else {
      // Scrolling up
      header.classList.remove('header-hidden');
      if (scrollTop > 50) {
        header.classList.add('header-sticky');
      } else {
        header.classList.remove('header-sticky');
      }
    }
    lastScrollTop = scrollTop;
  });
}

function initSmoothScrolling() {
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      e.preventDefault();
      const targetId = this.getAttribute('href');
      if (targetId === '#') return;
      
      const targetElement = document.querySelector(targetId);
      if (targetElement) {
        window.scrollTo({
          top: targetElement.offsetTop - 80,
          behavior: 'smooth'
        });
      }
    });
  });
  
  // Start journey button
  const ctaButton = document.querySelector('.cta-button');
  if (ctaButton) {
    ctaButton.addEventListener('click', () => {
      const speciesSection = document.getElementById('species');
      window.scrollTo({
        top: speciesSection.offsetTop - 80,
        behavior: 'smooth'
      });
    });
  }
}

function initCustomCursor() {
  const cursorOptions = ['default', 'banana', 'monkey-paw'];
  let currentCursor = 'default';
  
  // Create cursor element
  const cursor = document.createElement('div');
  cursor.className = 'custom-cursor';
  document.body.appendChild(cursor);
  
  // Update cursor position
  document.addEventListener('mousemove', (e) => {
    cursor.style.left = `${e.clientX}px`;
    cursor.style.top = `${e.clientY}px`;
  });
  
  // Toggle cursor on click (for demo purposes)
  cursor.addEventListener('click', () => {
    const nextIndex = (cursorOptions.indexOf(currentCursor) + 1) % cursorOptions.length;
    currentCursor = cursorOptions[nextIndex];
    cursor.className = `custom-cursor ${currentCursor}`;
  });
}

function initQuickFactsTicker() {
  const quickFacts = [
    "There are over 260 species of monkeys worldwide!",
    "The smallest monkey is the Pygmy Marmoset, weighing only 4 ounces!",
    "Some monkeys can jump up to 50 feet between trees!",
    "Monkeys use facial expressions similar to humans to communicate!",
    "The Mandrill is the world's largest monkey species!",
    "Some monkeys can recognize themselves in mirrors!"
  ];
  
  const factsContainer = document.querySelector('.quick-facts p');
  if (!factsContainer) return;
  
  let currentFactIndex = 0;
  
  function updateFact() {
    factsContainer.style.opacity = '0';
    
    setTimeout(() => {
      currentFactIndex = (currentFactIndex + 1) % quickFacts.length;
      factsContainer.textContent = `Did you know? ${quickFacts[currentFactIndex]}`;
      factsContainer.style.opacity = '1';
    }, 500);
  }
  
  // Initial display
  factsContainer.textContent = `Did you know? ${quickFacts[0]}`;
  
  // Rotate facts every 8 seconds
  setInterval(updateFact, 8000);
}

// ------ Species Gallery Functions ------
function initSpeciesFilter() {
  const filterButtons = document.querySelectorAll('.filter-button');
  const speciesCards = document.querySelectorAll('.species-card');
  
  filterButtons.forEach(button => {
    button.addEventListener('click', () => {
      // Update active button
      document.querySelector('.filter-button.active').classList.remove('active');
      button.classList.add('active');
      
      const filter = button.getAttribute('data-filter');
      
      // Filter the species cards
      speciesCards.forEach(card => {
        if (filter === 'all') {
          card.style.display = 'block';
        } else {
          const categories = card.getAttribute('data-category').split(' ');
          if (categories.includes(filter)) {
            card.style.display = 'block';
          } else {
            card.style.display = 'none';
          }
        }
      });
    });
  });
}

function initSpeciesCardInteraction() {
  const speciesCards = document.querySelectorAll('.species-card');
  
  speciesCards.forEach(card => {
    // Flip card effect
    card.addEventListener('click', () => {
      card.classList.toggle('flipped');
    });
    
    // Mouse enter/leave effects
    card.addEventListener('mouseenter', () => {
      card.classList.add('hover');
    });
    
    card.addEventListener('mouseleave', () => {
      card.classList.remove('hover');
      // Remove flipped state when mouse leaves
      setTimeout(() => {
        card.classList.remove('flipped');
      }, 300);
    });
  });
}

function initLoadMoreSpecies() {
  const loadMoreButton = document.querySelector('.load-more');
  if (!loadMoreButton) return;
  
  // Mock data for additional species
  const additionalSpecies = [
    {
      name: "Mandrill",
      description: "Known for their colorful faces and buttocks, mandrills are the largest monkey species.",
      image: "mandrill.jpg",
      region: "Central Africa",
      category: "old-world endangered"
    },
    {
      name: "Golden Lion Tamarin",
      description: "With their bright orange manes, these small monkeys are named after the king of beasts.",
      image: "tamarin.jpg",
      region: "Brazil",
      category: "new-world endangered"
    },
    {
      name: "Japanese Macaque",
      description: "Also known as 'snow monkeys,' they're famous for bathing in hot springs during winter.",
      image: "macaque.jpg",
      region: "Japan",
      category: "old-world"
    }
  ];
  
  let loadCount = 0;
  
  loadMoreButton.addEventListener('click', () => {
    if (loadCount >= additionalSpecies.length) {
      loadMoreButton.textContent = "No More Species to Load";
      loadMoreButton.disabled = true;
      return;
    }
    
    // Add a new species card
    const species = additionalSpecies[loadCount];
    const galleryContainer = document.querySelector('.species-gallery');
    
    const newCard = document.createElement('div');
    newCard.className = 'species-card';
    newCard.setAttribute('data-category', species.category);
    
    newCard.innerHTML = `
      <img src="${species.image}" alt="${species.name} in its natural habitat" class="species-image">
      <div class="species-info">
        <h3>${species.name}</h3>
        <p>${species.description}</p>
        <span class="region-tag">${species.region}</span>
      </div>
    `;
    
    // Add with animation
    newCard.style.opacity = '0';
    galleryContainer.appendChild(newCard);
    
    // Trigger reflow
    void newCard.offsetWidth;
    
    // Fade in
    newCard.style.opacity = '1';
    
    // Add the same interactions as existing cards
    newCard.addEventListener('click', () => {
      newCard.classList.toggle('flipped');
    });
    
    newCard.addEventListener('mouseenter', () => {
      newCard.classList.add('hover');
    });
    
    newCard.addEventListener('mouseleave', () => {
      newCard.classList.remove('hover');
      setTimeout(() => {
        newCard.classList.remove('flipped');
      }, 300);
    });
    
    loadCount++;
    
    // Update button text
    if (loadCount >= additionalSpecies.length) {
      loadMoreButton.textContent = "All Species Loaded";
    }
  });
}

// ------ Hero Section Animations ------
function animateHeroSection() {
  const monkeyImage = document.querySelector('.animated-monkey');
  if (!monkeyImage) return;
  
  // Add entrance animation
  monkeyImage.classList.add('swing-in');
  
  // Add subtle swing animation after entrance
  setTimeout(() => {
    monkeyImage.classList.remove('swing-in');
    monkeyImage.classList.add('subtle-swing');
  }, 2000);
}

// ------ Learning Zone Functions ------
function initLearningModules() {
  const moduleLinks = document.querySelectorAll('.module-link');
  
  moduleLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      
      const targetId = link.getAttribute('href').substring(1);
      
      // Check if we have local storage data for this module
      const progress = localStorage.getItem(`module-progress-${targetId}`) || '0';
      
      // For this demo, just show a notification with the module name and progress
      alert(`Loading module: ${link.parentElement.querySelector('h3').textContent}\nYour progress: ${progress}%`);
      
      // In a real implementation, you would load the module content or redirect
      // For now we'll just update the progress in localStorage
      const newProgress = Math.min(100, parseInt(progress) + 25);
      localStorage.setItem(`module-progress-${targetId}`, newProgress.toString());
    });
  });
}

function initEducatorResources() {
  const resourceLinks = document.querySelectorAll('.resource-list a');
  
  resourceLinks.forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      
      // Demo download simulation
      const resourceName = link.textContent;
      
      // Create a fake download progress indicator
      const progressBar = document.createElement('div');
      progressBar.className = 'download-progress';
      progressBar.innerHTML = `<div class="progress-text">Downloading ${resourceName}...</div>
                             <div class="progress-bar"><div class="progress-fill"></div></div>`;
      
      document.querySelector('.educator-resources').appendChild(progressBar);
      
      // Simulate progress
      let progress = 0;
      const interval = setInterval(() => {
        progress += 10;
        progressBar.querySelector('.progress-fill').style.width = `${progress}%`;
        
        if (progress >= 100) {
          clearInterval(interval);
          progressBar.querySelector('.progress-text').textContent = `${resourceName} downloaded!`;
          
          // Remove after a delay
          setTimeout(() => {
            progressBar.remove();
          }, 3000);
          
          // In a real implementation, you would initiate the actual file download
          console.log(`Resource downloaded: ${resourceName}`);
        }
      }, 200);
    });
  });
}

// ------ Habitat Explorer Functions ------
function initHabitatExplorer() {
  const habitats = document.querySelectorAll('.habitat-card');
  const prevButton = document.querySelector('.nav-button[data-direction="prev"]');
  const nextButton = document.querySelector('.nav-button[data-direction="next"]');
  
  if (!habitats.length || !prevButton || !nextButton) return;
  
  let currentHabitatIndex = 0;
  
  // Show only the current habitat
  function updateHabitatDisplay() {
    habitats.forEach((habitat, index) => {
      if (index === currentHabitatIndex) {
        habitat.classList.add('active');
        habitat.style.display = 'flex';
      } else {
        habitat.classList.remove('active');
        habitat.style.display = 'none';
      }
    });
  }
  
  // Initial display
  updateHabitatDisplay();
  
  // Navigation buttons
  prevButton.addEventListener('click', () => {
    currentHabitatIndex = (currentHabitatIndex - 1 + habitats.length) % habitats.length;
    updateHabitatDisplay();
  });
  
  nextButton.addEventListener('click', () => {
    currentHabitatIndex = (currentHabitatIndex + 1) % habitats.length;
    updateHabitatDisplay();
  });
  
  // Explore habitat buttons
  document.querySelectorAll('.explore-button').forEach(button => {
    button.addEventListener('click', function() {
      const habitat = this.closest('.habitat-card');
      
      // Toggle the immersive view
      habitat.classList.toggle('immersive-view');
      
      // Update button text
      if (habitat.classList.contains('immersive-view')) {
        this.textContent = 'Exit Immersive View';
        
        // Add hidden interactive elements in immersive view
        const hiddenElements = ['monkey', 'bird', 'butterfly', 'frog'];
        
        hiddenElements.forEach(element => {
          const hiddenEl = document.createElement('div');
          hiddenEl.className = `hidden-${element}`;
          hiddenEl.style.position = 'absolute';
          hiddenEl.style.top = `${Math.random() * 80 + 10}%`;
          hiddenEl.style.left = `${Math.random() * 80 + 10}%`;
          hiddenEl.style.cursor = 'pointer';
          
          // Add interaction
          hiddenEl.addEventListener('click', () => {
            alert(`You found a hidden ${element}! Great jungle explorer skills!`);
          });
          
          habitat.querySelector('.habitat-image').appendChild(hiddenEl);
        });
      } else {
        this.textContent = 'Explore This Habitat';
        
        // Remove hidden elements
        habitat.querySelectorAll('[class^="hidden-"]').forEach(el => {
          el.remove();
        });
      }
    });
  });
}

function initSoundControls() {
  const soundButtons = document.querySelectorAll('.sound-button');
  
  // Create audio elements
  const sounds = {
    'howler-call': new Audio('sounds/howler-monkey.mp3'),
    'proboscis-call': new Audio('sounds/proboscis-monkey.mp3')
  };
  
  // For demo purposes, we'll fake the audio
  Object.values(sounds).forEach(sound => {
    sound.volume = 0.5;
    sound.play = function() {
      console.log("Playing sound (simulated)");
      this.dispatchEvent(new Event('play'));
      
      // Simulate play duration
      setTimeout(() => {
        this.dispatchEvent(new Event('ended'));
      }, 5000);
    };
  });
  
  soundButtons.forEach(button => {
    button.addEventListener('click', function() {
      const soundId = this.getAttribute('data-sound');
      const sound = sounds[soundId];
      
      if (!sound) return;
      
      if (this.classList.contains('playing')) {
        // Stop the sound
        sound.pause();
        sound.currentTime = 0;
        this.classList.remove('playing');
        this.textContent = 'Play Sound';
      } else {
        // Play the sound
        sound.play();
        this.classList.add('playing');
        this.textContent = 'Stop Sound';
        
        // Reset button when sound ends
        sound.addEventListener('ended', () => {
          this.classList.remove('playing');
          this.textContent = 'Play Sound';
        }, { once: true });
      }
    });
  });
}

// ------ Conservation Section Functions ------
function initConservationInteractions() {
  const actionButton = document.querySelector('.action-button');
  
  if (actionButton) {
    actionButton.addEventListener('click', () => {
      // Modal creation for conservation action
      const modal = document.createElement('div');
      modal.className = 'conservation-modal';
      modal.innerHTML = `
        <div class="modal-content">
          <span class="close-modal">&times;</span>
          <h3>Support Monkey Conservation</h3>
          <p>Choose how you'd like to help:</p>
          <div class="action-options">
            <button class="action-option" data-action="adopt">Adopt a Monkey</button>
            <button class="action-option" data-action="donate">Make a Donation</button>
            <button class="action-option" data-action="volunteer">Volunteer Opportunities</button>
            <button class="action-option" data-action="educate">Educational Resources</button>
          </div>
        </div>
      `;
      
      document.body.appendChild(modal);
      
      // Close button functionality
      modal.querySelector('.close-modal').addEventListener('click', () => {
        modal.remove();
      });
      
      // Action options
      modal.querySelectorAll('.action-option').forEach(option => {
        option.addEventListener('click', () => {
          const action = option.getAttribute('data-action');
          alert(`You've selected: ${action}. In a real site, you would be directed to the appropriate page.`);
          modal.remove();
        });
      });
      
      // Close when clicking outside
      modal.addEventListener('click', (e) => {
        if (e.target === modal) {
          modal.remove();
        }
      });
    });
  }
  
  // Make success story cards interactive
  const storyCards = document.querySelectorAll('.story-card');
  storyCards.forEach(card => {
    card.addEventListener('click', () => {
      // Expand the card with more information
      card.classList.toggle('expanded');
      
      // In expanded state, add more content if needed
      if (card.classList.contains('expanded') && !card.querySelector('.expanded-content')) {
        const expandedContent = document.createElement('div');
        expandedContent.className = 'expanded-content';
        expandedContent.innerHTML = `
          <p>Learn more about this success story and the conservation efforts that made it possible.</p>
          <a href="#" class="read-more">Read the Full Story</a>
        `;
        card.appendChild(expandedContent);
      }
    });
  });
}

// ------ Design Section Functions ------
function initColorPaletteInteraction() {
  const colorSwatches = document.querySelectorAll('.color-swatch');
  
  colorSwatches.forEach(swatch => {
    swatch.addEventListener('click', function() {
      // Get the hex color
      const hexColor = this.querySelector('.color-hex').textContent;
      
      // Copy to clipboard
      navigator.clipboard.writeText(hexColor).then(() => {
        // Create and show a notification
        const notification = document.createElement('div');
        notification.className = 'copy-notification';
        notification.textContent = `${hexColor} copied to clipboard!`;
        notification.style.backgroundColor = hexColor;
        
        // Set text color based on background brightness
        const rgb = hexToRgb(hexColor);
        const brightness = (rgb.r * 299 + rgb.g * 587 + rgb.b * 114) / 1000;
        notification.style.color = brightness > 128 ? 'black' : 'white';
        
        document.body.appendChild(notification);
        
        // Remove after delay
        setTimeout(() => {
          notification.remove();
        }, 2000);
      });
    });
  });
  
  // Helper function to convert hex to RGB
  function hexToRgb(hex) {
    const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    return result ? {
      r: parseInt(result[1], 16),
      g: parseInt(result[2], 16),
      b: parseInt(result[3], 16)
    } : { r: 0, g: 0, b: 0 };
  }
}

function initArtworkGallery() {
  const galleryItems = document.querySelectorAll('.gallery-item');
  
  galleryItems.forEach(item => {
    item.addEventListener('click', function() {
      // Create lightbox
      const lightbox = document.createElement('div');
      lightbox.className = 'artwork-lightbox';
      
      const img = document.createElement('img');
      img.src = this.src;
      img.alt = this.alt;
      
      lightbox.appendChild(img);
      
      // Close button
      const closeButton = document.createElement('button');
      closeButton.className = 'lightbox-close';
      closeButton.innerHTML = '&times;';
      lightbox.appendChild(closeButton);
      
      document.body.appendChild(lightbox);
      
      // Prevent scrolling while lightbox is open
      document.body.style.overflow = 'hidden';
      
      // Close functionality
      closeButton.addEventListener('click', () => {
        lightbox.remove();
        document.body.style.overflow = '';
      });
      
      lightbox.addEventListener('click', (e) => {
        if (e.target === lightbox) {
          lightbox.remove();
          document.body.style.overflow = '';
        }
      });
    });
  });
  
  // Submit button functionality
  const submitButton = document.querySelector('.submit-button');
  if (submitButton) {
    submitButton.addEventListener('click', () => {
      // Create submission form modal
      const modal = document.createElement('div');
      modal.className = 'submission-modal';
      modal.innerHTML = `
        <div class="modal-content">
          <span class="close-modal">&times;</span>
          <h3>Submit Your Monkey Artwork</h3>
          <form id="artwork-form">
            <div class="form-group">
              <label for="artist-name">Your Name:</label>
              <input type="text" id="artist-name" required>
            </div>
            <div class="form-group">
              <label for="artwork-title">Artwork Title:</label>
              <input type="text" id="artwork-title" required>
            </div>
            <div class="form-group">
              <label for="artwork-description">Description:</label>
              <textarea id="artwork-description" rows="3"></textarea>
            </div>
            <div class="form-group">
              <label for="artwork-file">Upload Artwork (JPG, PNG):</label>
              <input type="file" id="artwork-file" accept=".jpg,.jpeg,.png" required>
            </div>
            <button type="submit" class="submit-artwork">Submit Artwork</button>
          </form>
        </div>
      `;
      
      document.body.appendChild(modal);
      
      // Close button functionality
      modal.querySelector('.close-modal').addEventListener('click', () => {
        modal.remove();
      });
      
      // Form submission
      modal.querySelector('#artwork-form').addEventListener('submit', (e) => {
        e.preventDefault();
        
        // Get form values
        const artistName = modal.querySelector('#artist-name').value;
        const artworkTitle = modal.querySelector('#artwork-title').value;
        
        // Show success message
        alert(`Thank you, ${artistName}! Your artwork "${artworkTitle}" has been submitted for review.`);
        modal.remove();
      });
      
      // Close when clicking outside
      modal.addEventListener('click', (e) => {
        if (e.target === modal) {
          modal.remove();
        }
      });
    });
  }
}

function initDesignChallengeForm() {
  const challengeButton = document.querySelector('.challenge-button');
  
  if (challengeButton) {
    challengeButton.addEventListener('click', () => {
      alert('The design challenge form would open here. Users could submit entries and view participation details.');
    });
  }
}

// ------ Footer Functions ------
function initSubscriptionForm() {
  const subscribeForm = document.querySelector('.subscribe-form');
  
  if (subscribeForm) {
    subscribeForm.addEventListener('submit', (e) => {
      e.preventDefault();
      
      const emailInput = subscribeForm.querySelector('.email-input');
      const email = emailInput.value.trim();
      
      // Basic validation
      if (!email || !isValidEmail(email)) {
        showFormError(emailInput, 'Please enter a valid email address');
        return;
      }
      
      // Show success message
      const successMessage = document.createElement('p');
      successMessage.className = 'subscribe-success';
      successMessage.textContent = `Thanks for subscribing! A confirmation has been sent to ${email}`;
      
      // Replace form with success message
      subscribeForm.innerHTML = '';
      subscribeForm.appendChild(successMessage);
    });
  }
  
  function isValidEmail(email) {
    const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return regex.test(email);
  }
  
  function showFormError(inputElement, message) {
    // Remove any existing error
    const existingError = inputElement.parentElement.querySelector('.form-error');
    if (existingError) {
      existingError.remove();
    }
    
    // Create and add error message
    const errorElement = document.createElement('span');
    errorElement.className = 'form-error';
    errorElement.textContent = message;
    
    inputElement.parentElement.appendChild(errorElement);
    inputElement.classList.add('input-error');
    
    // Remove error when input changes
    inputElement.addEventListener('input', () => {
      errorElement.remove();
      inputElement.classList.remove('input-error');
    }, { once: true });
  }
}

// ------ Accessibility Features ------
function initAccessibilityFeatures() {
  // Create accessibility controls
  const accessibilityButton = document.createElement('button');
  accessibilityButton.className = 'accessibility-toggle';
  accessibilityButton.setAttribute('aria-label', 'Accessibility Options');
  accessibilityButton.innerHTML = '<span class="sr-only">Accessibility</span>A';
  document.body.appendChild(accessibilityButton);
  
  // Accessibility panel
  const accessibilityPanel = document.createElement('div');
  accessibilityPanel.className = 'accessibility-panel';
  accessibilityPanel.innerHTML = `
    <h3>Accessibility Options</h3>
    <div class="accessibility-option">
      <label for="font-size">Font Size:</label>
      <div class="font-controls">
        <button class="font-decrease" aria-label="Decrease Font Size">A-</button>
        <span class="current-size">100%</span>
        <button class="font-increase" aria-label="Increase Font Size">A+</button>
      </div>
    </div>
    <div class="accessibility-option">
      <label for="contrast-mode">High Contrast:</label>
      <input type="checkbox" id="contrast-mode" class="toggle-input">
      <label for="contrast-mode" class="toggle-label"></label>
    </div>
    <div class="accessibility-option">
      <label for="motion-reduce">Reduce Motion:</label>
      <input type="checkbox" id="motion-reduce" class="toggle-input">
      <label for="motion-reduce" class="toggle-label"></label>
    </div>
  `;
  
  accessibilityButton.addEventListener('click', () => {
    if (document.body.contains(accessibilityPanel)) {
      accessibilityPanel.remove();
    } else {
      document.body.appendChild(accessibilityPanel);
    }
  });
  
  // Close panel when clicking outside
  document.addEventListener('click', (e) => {
    if (document.body.contains(accessibilityPanel) && 
        !accessibilityPanel.contains(e.target) && 
        e.target !== accessibilityButton) {
      accessibilityPanel.remove();
    }
  });
  
  // Implement the accessibility features when the panel is added to the DOM
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      if (mutation.addedNodes && mutation.addedNodes.length) {
        for (let i = 0; i < mutation.addedNodes.length; i++) {
          const node = mutation.addedNodes[i];
          if (node === accessibilityPanel) {
            initFontSizeControls();
            initContrastMode();
            initReduceMotion();
          }
        }
      }
    });
  });
  
  observer.observe(document.body, { childList: true });
  
  function initFontSizeControls() {
    const decreaseBtn = accessibilityPanel.querySelector('.font-decrease');
    const increaseBtn = accessibilityPanel.querySelector('.font-increase');
    const sizeDisplay = accessibilityPanel.querySelector('.current-size');
    
    let currentSize = parseInt(localStorage.getItem('font-size-percentage') || '100');
    sizeDisplay.textContent = currentSize + '%';
    
    // Apply saved font size
    document.documentElement.style.fontSize = `${currentSize}%`;
    
    decreaseBtn.addEventListener('click', () => {
      if (currentSize > 80) {
        currentSize -= 10;
        updateFontSize();
      }
    });
    
    increaseBtn.addEventListener('click', () => {
      if (currentSize < 150) {
        currentSize += 10;
        updateFontSize();
      }
    });
    
    function updateFontSize() {
      document.documentElement.style.fontSize = `${currentSize}%`;
      sizeDisplay.textContent = currentSize + '%';
      localStorage.setItem('font-size-percentage', currentSize.toString());
    }
  }
  
  function initContrastMode() {
    const contrastToggle = accessibilityPanel.querySelector('#contrast-mode');
    
    // Check saved preference
    const highContrast = localStorage.getItem('high-contrast') === 'true';
    contrastToggle.checked = highContrast;
    
    if (highContrast) {
      document.body.classList.add('high-contrast');
    }
    
    contrastToggle.addEventListener('change', () => {
      document.body.classList.toggle('high-contrast', contrastToggle.checked);
      localStorage.setItem('high-contrast', contrastToggle.checked.toString());
    });
  }
  
  function initReduceMotion() {
    const motionToggle = accessibilityPanel.querySelector('#motion-reduce');
    
    // Check saved preference
    const reduceMotion = localStorage.getItem('reduce-motion') === 'true';
    motionTog