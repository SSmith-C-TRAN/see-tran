// main.js - Core application JavaScript utilities
// Transit Intelligence Platform

// =============================================================================
// TOAST NOTIFICATION SYSTEM
// =============================================================================

/**
 * Show toast notification with app-themed styling
 * @param {string} message - The message to display
 * @param {boolean} isSuccess - Whether this is a success (true) or error (false) message
 * @param {number} duration - Duration in milliseconds (default: 3000)
 */
function showToast(message, isSuccess = true, duration = 3000) {
    // Remove existing toast if any
    const existingToast = document.querySelector('.app-toast');
    if (existingToast) {
        existingToast.remove();
    }

    // Create the toast element with app theme
    const toast = document.createElement('div');
    toast.className = 'app-toast fixed top-4 left-1/2 transform -translate-x-1/2 z-50 max-w-md';
    
    // Apply app-themed styling
    const bgClass = isSuccess 
        ? 'bg-gradient-to-r from-green-600 to-emerald-600' 
        : 'bg-gradient-to-r from-red-600 to-rose-600';
    
    toast.innerHTML = `
        <div class="${bgClass} backdrop-blur-lg border border-white/20 rounded-xl px-6 py-4 shadow-2xl">
            <div class="flex items-center space-x-3">
                <div class="flex-shrink-0">
                    ${isSuccess ? `
                        <svg class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                        </svg>
                    ` : `
                        <svg class="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
                        </svg>
                    `}
                </div>
                <div class="flex-1">
                    <p class="text-white font-medium text-sm">${message}</p>
                </div>
                <button onclick="this.closest('.app-toast').remove()" class="flex-shrink-0 text-white/70 hover:text-white transition-colors">
                    <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
                    </svg>
                </button>
            </div>
        </div>
    `;

    // Set initial state
    toast.style.opacity = '0';
    toast.style.transform = 'translate(-50%, -20px)';
    toast.style.transition = 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)';

    // Append to body
    document.body.appendChild(toast);

    // Animate in
    requestAnimationFrame(() => {
        toast.style.opacity = '1';
        toast.style.transform = 'translate(-50%, 0)';
    });

    // Auto-hide after duration
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translate(-50%, -20px)';
        setTimeout(() => {
            if (toast.parentNode) {
                toast.remove();
            }
        }, 300);
    }, duration);
}

// =============================================================================
// HTMX RESPONSE HANDLING
// =============================================================================

/**
 * Handle HTMX responses and show appropriate toast notifications
 * @param {Event} event - HTMX afterRequest event
 */
function handleHtmxResponse(event) {
    const xhr = event.detail.xhr;
    const response = xhr.response;
    
    try {
        // Try to parse JSON response
        const data = JSON.parse(response);
        
        if (data.status === 'success') {
            showToast(data.message, true);
        } else if (data.status === 'error') {
            showToast(data.message, false);
        }
    } catch (e) {
        // Not JSON response, check status codes
        if (xhr.status >= 400) {
            showToast('An error occurred. Please try again.', false);
        }
    }
}

/**
 * Handle HTMX request errors
 * @param {Event} event - HTMX responseError event
 */
function handleHtmxError(event) {
    const xhr = event.detail.xhr;
    let message = 'Network error. Please check your connection.';
    
    if (xhr.status === 404) {
        message = 'Resource not found.';
    } else if (xhr.status === 500) {
        message = 'Server error. Check your network connection.';
    } else if (xhr.status === 403) {
        message = 'You do not have permission to perform this action.';
    }
    
    showToast(message, false);
}

// =============================================================================
// FILTER MANAGEMENT
// =============================================================================

/**
 * Get current filter state from form elements
 * @param {string} formSelector - CSS selector for the filter form
 * @returns {Object} Current filter values
 */
function getFilterState(formSelector = '#vendor-filters') {
    const form = document.querySelector(formSelector);
    if (!form) return {};
    
    const formData = new FormData(form);
    const filters = {};
    
    for (const [key, value] of formData.entries()) {
        if (value && value.trim() !== '') {
            filters[key] = value.trim();
        }
    }
    
    return filters;
}

/**
 * Clear all filters and refresh the list
 * @param {string} formSelector - CSS selector for the filter form
 * @param {string} listSelector - CSS selector for the list to refresh
 */
function clearAllFilters(formSelector = '#vendor-filters', listSelector = '#vendors-list') {
    const form = document.querySelector(formSelector);
    if (form) {
        // Reset form elements
        form.reset();
        
        // Clear any custom selections
        const selects = form.querySelectorAll('select');
        selects.forEach(select => {
            select.selectedIndex = 0;
        });
        
        // Trigger refresh
        const listElement = document.querySelector(listSelector);
        if (listElement && typeof htmx !== 'undefined') {
            htmx.trigger(listElement, 'refresh');
        }
    }
}

/**
 * Apply filter badge display
 * @param {Object} filters - Current filter state
 * @param {string} badgeContainer - CSS selector for badge container
 */
function updateFilterBadges(filters, badgeContainer = '#active-filters') {
    const container = document.querySelector(badgeContainer);
    if (!container) return;
    
    container.innerHTML = '';
    
    Object.entries(filters).forEach(([key, value]) => {
        if (value && value !== '') {
            const badge = document.createElement('span');
            badge.className = 'inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-purple-600/20 text-purple-300 border border-purple-600/30';
            badge.innerHTML = `
                ${key}: ${value}
                <button onclick="clearFilter('${key}')" class="ml-1 text-purple-400 hover:text-purple-200">
                    <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                        <path fill-rule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clip-rule="evenodd"/>
                    </svg>
                </button>
            `;
            container.appendChild(badge);
        }
    });
}

/**
 * Clear a specific filter
 * @param {string} filterKey - The filter key to clear
 * @param {string} formSelector - CSS selector for the filter form
 */
function clearFilter(filterKey, formSelector = '#vendor-filters') {
    const form = document.querySelector(formSelector);
    if (form) {
        const element = form.querySelector(`[name="${filterKey}"]`);
        if (element) {
            element.value = '';
            
            // Trigger change event to update the list
            element.dispatchEvent(new Event('change', { bubbles: true }));
        }
    }
}

// =============================================================================
// FORM UTILITIES
// =============================================================================

/**
 * Reset form and clear validation errors
 * @param {string} formSelector - CSS selector for the form
 */
function resetFormWithValidation(formSelector) {
    const form = document.querySelector(formSelector);
    if (form) {
        form.reset();
        
        // Clear validation error messages
        const errorElements = form.querySelectorAll('.text-red-400, .border-red-500');
        errorElements.forEach(element => {
            if (element.classList.contains('text-red-400')) {
                element.remove();
            } else {
                element.classList.remove('border-red-500');
                element.classList.add('border-slate-700');
            }
        });
    }
}

/**
 * Show form validation errors
 * @param {Object} errors - Object with field names as keys and error messages as values
 * @param {string} formSelector - CSS selector for the form
 */
function showFormValidationErrors(errors, formSelector) {
    const form = document.querySelector(formSelector);
    if (!form) return;
    
    // Clear existing errors first
    resetFormWithValidation(formSelector);
    
    Object.entries(errors).forEach(([fieldName, errorMessage]) => {
        const field = form.querySelector(`[name="${fieldName}"]`);
        if (field) {
            // Add error styling to field
            field.classList.add('border-red-500');
            field.classList.remove('border-slate-700');
            
            // Add error message
            const errorDiv = document.createElement('div');
            errorDiv.className = 'text-red-400 text-xs mt-1';
            errorDiv.textContent = errorMessage;
            
            const parent = field.parentNode;
            parent.appendChild(errorDiv);
        }
    });
}

// =============================================================================
// LOADING STATES
// =============================================================================

/**
 * Show loading state on an element
 * @param {string} selector - CSS selector for the element
 * @param {string} loadingText - Text to show while loading
 */
function showLoading(selector, loadingText = 'Loading...') {
    const element = document.querySelector(selector);
    if (element) {
        element.dataset.originalContent = element.innerHTML;
        element.innerHTML = `
            <div class="flex items-center justify-center space-x-2 text-slate-400">
                <svg class="animate-spin h-4 w-4" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span class="text-sm">${loadingText}</span>
            </div>
        `;
    }
}

/**
 * Hide loading state and restore original content
 * @param {string} selector - CSS selector for the element
 */
function hideLoading(selector) {
    const element = document.querySelector(selector);
    if (element && element.dataset.originalContent) {
        element.innerHTML = element.dataset.originalContent;
        delete element.dataset.originalContent;
    }
}

// =============================================================================
// INITIALIZATION
// =============================================================================

/**
 * Initialize the application
 */
function initializeApp() {
    // Set up HTMX event listeners
    if (typeof htmx !== 'undefined') {
        // Handle successful responses with toast notifications
        document.body.addEventListener('htmx:afterRequest', handleHtmxResponse);
        
        // Handle request errors
        document.body.addEventListener('htmx:responseError', handleHtmxError);
        
        // Show loading states
        document.body.addEventListener('htmx:beforeRequest', (event) => {
            const target = event.target;
            if (target.classList.contains('show-loading')) {
                showLoading('#' + target.id, 'Processing...');
            }
        });
        
        // Hide loading states
        document.body.addEventListener('htmx:afterRequest', (event) => {
            const target = event.target;
            if (target.classList.contains('show-loading')) {
                hideLoading('#' + target.id);
            }
        });
    }

    // Delegated click handler for product picker options (robust across HTMX swaps)
    document.body.addEventListener('click', (event) => {
        const li = event.target.closest('#product-options li[data-product-id]');
        if (!li) return;

        const form = li.closest('form');
        if (!form) return;

        const productId = li.dataset.productId;
        const productName = li.dataset.productName;
        const vendorName = li.dataset.vendorName || '';

        // Set the hidden input value
        const hiddenInput = form.querySelector('input[name="product_id"]');
        if (hiddenInput) {
            hiddenInput.value = productId;
        }

        // Show the selection pill
        const selectionPill = form.querySelector('#product-selection-pill');
        const pillText = selectionPill.querySelector('span');
        if (selectionPill && pillText) {
            pillText.textContent = vendorName ? `${productName} • ${vendorName}` : productName;
            selectionPill.classList.remove('hidden');
        }

        // Hide the search input and results
        const searchContainer = form.querySelector('#product-search-container');
        if (searchContainer) {
            searchContainer.classList.add('hidden');
        }
        
        // Clear the results list
        const productOptions = form.querySelector('#product-options');
        if (productOptions) {
            productOptions.innerHTML = '';
        }
    });
    
    console.log('🚀 Transit Intelligence Platform - Application initialized');
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}

// Attach CSRF token to all HTMX requests
if (typeof htmx !== 'undefined') {
    document.body.addEventListener('htmx:configRequest', function (event) {
        const tokenMeta = document.querySelector('meta[name="csrf-token"]');
        if (tokenMeta) {
            event.detail.headers['X-CSRFToken'] = tokenMeta.getAttribute('content');
        }
    });
}

// =============================================================================
// GLOBAL UTILITIES
// =============================================================================

// Make key functions available globally
window.showToast = showToast;
window.clearAllFilters = clearAllFilters;
window.clearFilter = clearFilter;
window.resetFormWithValidation = resetFormWithValidation;
window.showFormValidationErrors = showFormValidationErrors;