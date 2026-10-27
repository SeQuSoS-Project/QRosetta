// Manual page (docs.html): highlights the table-of-contents entry of the section in view, and
// makes each table's sideways-scrolling box a named region that takes keyboard focus.
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

    var headings = Array.prototype.slice.call(document.querySelectorAll('.doc-prose h2, .doc-prose h3, .doc-prose h4'));
    var seen = {};
    Array.prototype.forEach.call(document.querySelectorAll('.table-scroll'), function (box) {
        var name = 'Table';
        headings.forEach(function (h) {
            if (h.compareDocumentPosition(box) & Node.DOCUMENT_POSITION_FOLLOWING) name = 'Table: ' + h.textContent.trim();
        });
        seen[name] = (seen[name] || 0) + 1;
        box.tabIndex = 0;
        box.setAttribute('role', 'region');
        box.setAttribute('aria-label', seen[name] > 1 ? name + ' (' + seen[name] + ')' : name);
    });
})();
