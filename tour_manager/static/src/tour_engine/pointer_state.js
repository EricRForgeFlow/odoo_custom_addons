import { debounce } from "@web/core/utils/timing";
import { TourPointer } from "@web_tour/js/tour_pointer/tour_pointer";
import { createPointerState } from "@web_tour/js/tour_pointer/tour_pointer_state";
import { getScrollParent } from "@web_tour/js/utils/tour_utils";

/** Time (ms) the content of the pointer stays open after the mouse left it. */
const CLOSE_DELAY = 300;

/**
 * The engine of web_tour 20.0 drives the tour pointer through a shared state
 * whose fields it assigns (the element pointed to, the content, ...). The
 * pointer of 19.0 is driven by the methods of `createPointerState()` instead:
 * this object has the API of 20.0, and redraws the pointer of 19.0 after its
 * fields are assigned.
 */
class PointerState {
    _trigger;
    _content;
    _position;
    _isZone = false;
    _onClick;
    _pointer = null;
    _removeOverlay = () => {};
    _detach = () => {};
    _attachedTo = null;
    _scheduled = false;
    _closeTimeout;

    /** The element of the current step, which the robot acts on. */
    get trigger() {
        return this._trigger;
    }
    set trigger(value) {
        this._trigger = value;
        this._schedule();
    }
    get content() {
        return this._content;
    }
    set content(value) {
        this._content = value;
        this._schedule();
    }
    get position() {
        return this._position;
    }
    set position(value) {
        this._position = value;
        this._schedule();
    }
    get isZone() {
        return this._isZone;
    }
    set isZone(value) {
        this._isZone = Boolean(value);
        this._schedule();
    }
    /** Called when the pointer is clicked. */
    get onClick() {
        return this._onClick;
    }
    set onClick(value) {
        this._onClick = value;
        this._schedule();
    }

    /**
     * @param {Object} overlay the overlay service
     */
    mount(overlay) {
        this.unmount();
        this._pointer = createPointerState();
        this._removeOverlay = overlay.add(
            TourPointer,
            { pointerState: this._pointer.state, bounce: true },
            { sequence: 1100 } // sequence based on bootstrap z-index values.
        );
    }

    unmount() {
        clearTimeout(this._closeTimeout);
        this._detach();
        this._removeOverlay();
        this._removeOverlay = () => {};
        this._pointer?.destroy();
        this._pointer = null;
        this._trigger = this._content = this._onClick = undefined;
    }

    _schedule() {
        if (!this._scheduled) {
            this._scheduled = true;
            Promise.resolve().then(() => {
                this._scheduled = false;
                this.update();
            });
        }
    }

    /** Points to the current element with the current content, or hides the pointer. */
    update() {
        const pointer = this._pointer;
        if (!pointer) {
            return;
        }
        if (this._attachedTo !== this._trigger) {
            this._attach(this._trigger);
        }
        if (!this._trigger?.isConnected) {
            pointer.hide();
            return;
        }
        pointer.pointTo(
            this._trigger,
            { content: this._content ? String(this._content) : "", tooltipPosition: this._position },
            this._isZone
        );
        const extra = {
            onMouseEnter: () => this._open(),
            onMouseLeave: () => this._close(),
        };
        // When the element is out of view, the pointer of 19.0 points to the
        // edge of the screen, and scrolls to the element when clicked.
        if (pointer.state.anchor === this._trigger) {
            extra.onClick = this._onClick || null;
        }
        pointer.setState(extra);
    }

    _open() {
        clearTimeout(this._closeTimeout);
        this._pointer?.showContent(true);
    }

    /**
     * Closes the content of the pointer after a while, so that the mouse can go
     * from the element to the content (e.g. to its "Stop Tour" button), which
     * keeps it open: the pointer of 19.0 closes it as soon as the element is
     * left, the one of 20.0 keeps it open while it's reached.
     */
    _close() {
        clearTimeout(this._closeTimeout);
        this._closeTimeout = setTimeout(() => this._pointer?.showContent(false), CLOSE_DELAY);
    }

    /**
     * Opens the content of the pointer when the element is hovered, and moves
     * the pointer when the element is scrolled, as the engine of 19.0 does.
     *
     * @param {HTMLElement} [element]
     */
    _attach(element) {
        this._detach();
        this._attachedTo = element || null;
        if (!element) {
            return;
        }
        const open = () => this._open();
        const close = () => this._close();
        const onScroll = debounce(() => this.update(), 50);
        const scrollParent = getScrollParent(element);
        element.addEventListener("mouseenter", open);
        element.addEventListener("mouseleave", close);
        scrollParent?.addEventListener("scroll", onScroll);
        this._detach = () => {
            element.removeEventListener("mouseenter", open);
            element.removeEventListener("mouseleave", close);
            scrollParent?.removeEventListener("scroll", onScroll);
            this._attachedTo = null;
            this._detach = () => {};
        };
    }
}

export const pointerState = new PointerState();
