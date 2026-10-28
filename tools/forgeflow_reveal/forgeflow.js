// Copyright 2026 ForgeFlow S.L. (https://www.forgeflow.com)
// License OPL-1 (https://www.odoo.com/documentation/master/legal/licenses.html).
/* global Reveal, RevealNotes */

/**
 * A ForgeFlow deck: reveal.js at 1920 x 1080 with the theme's defaults, and
 * a small API to drive it from outside (a recording, a PDF print):
 *
 *   ForgeFlowDeck.init()        start the deck (call once)
 *   ForgeFlowDeck.ready()       a promise, resolved when the deck is ready
 *   ForgeFlowDeck.slides()      [{id, kind, steps}] in order
 *   ForgeFlowDeck.goTo(i)       slide i, before its first animation step
 *   ForgeFlowDeck.step()        the next animation step of the slide
 *   ForgeFlowDeck.complete(i)   slide i with every step shown
 *
 * With ``?record`` in the URL the deck has no controls nor progress bar.
 */
window.ForgeFlowDeck = {
    init(options = {}) {
        const record = new URLSearchParams(window.location.search).has("record");
        if (record) {
            document.documentElement.classList.add("ff-record");
        }
        this._ready = Reveal.initialize({
            width: 1920,
            height: 1080,
            margin: 0,
            minScale: 0.05,
            maxScale: 4,
            center: false,
            hash: !record,
            controls: !record,
            progress: !record,
            keyboard: !record,
            slideNumber: false,
            transition: "fade",
            backgroundTransition: "fade",
            pdfSeparateFragments: false,
            pdfMaxPagesPerSlide: 1,
            plugins: typeof RevealNotes === "undefined" ? [] : [RevealNotes],
            ...options,
        });
        return this._ready;
    },

    ready() {
        return this._ready || Promise.resolve();
    },

    _steps(section) {
        const indexes = new Set(
            [...section.querySelectorAll(".fragment")].map(
                (el) => el.getAttribute("data-fragment-index") || el
            )
        );
        return indexes.size;
    },

    slides() {
        return Reveal.getSlides().map((section) => ({
            id: section.dataset.id || "",
            kind: section.dataset.kind || "",
            steps: this._steps(section),
        }));
    },

    goTo(index) {
        Reveal.slide(index, 0, -1);
    },

    step() {
        return Reveal.nextFragment();
    },

    complete(index) {
        const steps = this._steps(Reveal.getSlides()[index]);
        Reveal.slide(index, 0, steps - 1);
    },
};
