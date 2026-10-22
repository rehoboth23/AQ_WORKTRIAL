// Client-side search module
(function() {
    'use strict';

    var searchInput = document.getElementById('search-input');
    var searchResults = document.getElementById('search-results');

    if (!searchInput || !searchResults) {
        return;
    }

    // Debounce helper
    function debounce(fn, delay) {
        var timer = null;
        return function() {
            var context = this;
            var args = arguments;
            clearTimeout(timer);
            timer = setTimeout(function() {
                fn.apply(context, args);
            }, delay);
        };
    }

    // Simple search implementation
    var handleInput = debounce(function() {
        var query = searchInput.value.toLowerCase().trim();
        if (query.length < 2) {
            searchResults.innerHTML = '';
            return;
        }
        searchResults.innerHTML = '<p class="search-hint">Searching for: ' + query + '</p>';
    }, 300);

    searchInput.addEventListener('input', handleInput);

    console.log('Search module loaded');
})();
