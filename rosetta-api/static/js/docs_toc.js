// Manual page (docs.html): highlights the table-of-contents entry of the section in view.
// Loaded as a classic script with defer; no imports.

(function () {
    var links = Array.prototype.slice.call(document.querySelectorAll('.toc-link'));
    var sections = links.map(function (l) { return document.querySelector(l.getAttribute('href')); });
    function onScroll() {
        var y = window.scrollY + 90;
        var idx = 0;
        for (var i = 0; i < sections.length; i++) {
            if (sections[i] && sections[i].offsetTop <= y) idx = i;
        }
        links.forEach(function (l, i) { l.classList.toggle('active', i === idx); });
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
})();
