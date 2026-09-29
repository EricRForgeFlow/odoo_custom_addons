"""Driving a real browser from Python, with trusted mouse and keyboard input.

The tour recorder and the leave warning ignore untrusted events (e.g. the ones
of Odoo's test tours, or of the clicks they replay themselves), and most flows
reload the page (starting a replay, a check or a recording), which would stop a
test script running in the page. So these tests drive Odoo's test browser (see
``HttpCase.browser_js``) through the Chrome DevTools protocol instead: the
input sent this way is trusted, like a user's.

The browser is Chrome or Chromium, found in the PATH or at ``ODOO_BROWSER_BIN``.
"""

import contextlib
import json
import time
from unittest.mock import patch
from urllib.parse import urljoin

from odoo.tests import HttpCase
from odoo.tests.common import ChromeBrowser, flushing_cursor

KEYS = {
    'Enter': {'code': 'Enter', 'windowsVirtualKeyCode': 13, 'text': '\r'},
    'Tab': {'code': 'Tab', 'windowsVirtualKeyCode': 9},
    'Escape': {'code': 'Escape', 'windowsVirtualKeyCode': 27},
}

# Finds the elements matching a CSS selector, optionally containing a text,
# that are visible; defines `__find(selector, text)` in the page.
FIND_JS = """
window.__find = (selector, text) => [...document.querySelectorAll(selector)].filter((el) => {
    const rect = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden'
        && (!text || el.innerText.includes(text) || (el.value || '').includes(text));
})"""


class BrowserError(AssertionError):
    pass


class Browser:
    """A page of Odoo's test browser, with Playwright-like helpers."""

    def __init__(self, case, chrome):
        self.case = case
        self.chrome = chrome

    # ------------------------------------------------------------------
    # Pages and scripts
    # ------------------------------------------------------------------

    def goto(self, path):
        self.chrome.navigate_to(urljoin(self.case.base_url(), path), wait_stop=True)
        self.wait_until("document.readyState === 'complete'")

    def evaluate(self, expression):
        """Evaluate a JavaScript expression in the page and return its value."""
        self.check_errors()
        response = self.chrome._websocket_request('Runtime.evaluate', params={
            'expression': expression,
            'awaitPromise': True,
            'returnByValue': True,
        }, timeout=30)
        if response.get('exceptionDetails'):
            raise BrowserError(f"{expression}: {response['exceptionDetails']}")
        return response['result'].get('value')

    def wait_until(self, condition, timeout=20, message=None):
        """Wait until a JavaScript condition is truthy; returns its value."""
        end = time.time() + timeout
        while True:
            # Errors in the browser fail right away; errors evaluating the
            # condition (e.g. the page is loading) mean it's not met yet.
            self.check_errors()
            try:
                value = self.evaluate(f"(() => {{ try {{ return {condition}; }} catch {{ return false; }} }})()")
            except (BrowserError, TimeoutError):
                self.check_errors()
                value = False
            if value:
                return value
            if time.time() > end:
                raise BrowserError(message or f"Timeout waiting for: {condition}")
            time.sleep(0.1)

    def check_errors(self):
        """Fail on the errors logged in the browser's console (see ChromeBrowser)."""
        result = self.chrome._result
        if result.done() and not result.cancelled() and result.exception():
            raise BrowserError(f"Error in the browser: {result.exception()}")

    def local_storage(self, key):
        return self.evaluate(f"localStorage.getItem({json.dumps(key)})")

    # ------------------------------------------------------------------
    # Elements
    # ------------------------------------------------------------------

    def _find_expr(self, selector, text=None, index=0):
        return (f"({FIND_JS}, __find({json.dumps(selector)}, {json.dumps(text)})[{index}])")

    def wait_for(self, selector, text=None, timeout=20):
        """Wait for a visible element matching `selector` (and containing `text`)."""
        self.wait_until(f"!!{self._find_expr(selector, text)}", timeout=timeout,
                        message=f"Element not found: {selector}" + (f" with text {text!r}" if text else ""))

    def wait_for_absent(self, selector, text=None, timeout=20):
        self.wait_until(f"!{self._find_expr(selector, text)}", timeout=timeout,
                        message=f"Element still there: {selector}" + (f" with text {text!r}" if text else ""))

    def count(self, selector, text=None):
        return self.evaluate(f"({FIND_JS}, __find({json.dumps(selector)}, {json.dumps(text)}).length)")

    def text(self, selector, text=None):
        self.wait_for(selector, text)
        return self.evaluate(f"{self._find_expr(selector, text)}.innerText")

    def value(self, selector):
        self.wait_for(selector)
        return self.evaluate(f"{self._find_expr(selector)}.value")

    def _center(self, selector, text=None, index=0, scroll=True, inner=None):
        if inner:
            self.wait_until(f"!!{self._find_expr(selector, text, index)}?.querySelector({json.dumps(inner)})",
                            message=f"Element not found: {inner} in {selector} with text {text!r}")
        else:
            self.wait_for(selector, text)
        element = self._find_expr(selector, text, index)
        if inner:
            element = f"{element}.querySelector({json.dumps(inner)})"
        return self.evaluate(f"""(() => {{
            const el = {element};
            if ({json.dumps(scroll)}) {{
                el.scrollIntoView({{ block: 'center', inline: 'center' }});
            }}
            const rect = el.getBoundingClientRect();
            return [rect.x + rect.width / 2, rect.y + rect.height / 2];
        }})()""")

    def _mouse(self, event_type, x, y, **params):
        self.chrome._websocket_request('Input.dispatchMouseEvent', params={
            'type': event_type, 'x': x, 'y': y, **params,
        })

    def hover(self, selector, text=None):
        x, y = self._center(selector, text)
        self._mouse('mouseMoved', x, y)

    def click(self, selector, text=None, index=0, inner=None):
        """Click the element like a user: moving the mouse to it, pressing and
        releasing the left button (trusted events). With `inner`, click the
        element matching it inside the one matching `selector` and `text`."""
        x, y = self._center(selector, text, index, inner=inner)
        self._mouse('mouseMoved', x, y)
        self._mouse('mousePressed', x, y, button='left', buttons=1, clickCount=1)
        self._mouse('mouseReleased', x, y, button='left', buttons=0, clickCount=1)
        time.sleep(0.1)

    def drag(self, selector, target_selector, target_text=None, steps=10):
        # Both positions are computed before pressing: scrolling during the
        # drag would move the page under the pointer.
        self._center(selector)
        x1, y1 = self._center(target_selector, target_text, scroll=False)
        x0, y0 = self._center(selector, scroll=False)
        self._mouse('mouseMoved', x0, y0)
        self._mouse('mousePressed', x0, y0, button='left', buttons=1, clickCount=1)
        for step in range(1, steps + 1):
            self._mouse('mouseMoved', x0 + (x1 - x0) * step / steps, y0 + (y1 - y0) * step / steps,
                        button='left', buttons=1)
            time.sleep(0.03)
        self._mouse('mouseReleased', x1, y1, button='left', buttons=0, clickCount=1)
        time.sleep(0.1)

    def type(self, text):
        """Type `text` in the focused element (trusted input events)."""
        for char in text:
            self.chrome._websocket_request('Input.insertText', params={'text': char})
        time.sleep(0.1)

    def press(self, key):
        params = {'key': key, **KEYS[key]}
        self.chrome._websocket_request('Input.dispatchKeyEvent', params={'type': 'keyDown', **params})
        self.chrome._websocket_request('Input.dispatchKeyEvent', params={
            'type': 'keyUp', **{k: v for k, v in params.items() if k != 'text'}})
        time.sleep(0.1)

    def select_all(self):
        self.chrome._websocket_request('Input.dispatchKeyEvent', params={
            'type': 'keyDown', 'key': 'a', 'code': 'KeyA', 'modifiers': 2, 'windowsVirtualKeyCode': 65,
            'commands': ['selectAll']})
        self.chrome._websocket_request('Input.dispatchKeyEvent', params={
            'type': 'keyUp', 'key': 'a', 'code': 'KeyA', 'modifiers': 2, 'windowsVirtualKeyCode': 65})


class TourManagerBrowserCase(HttpCase):
    """Base class of the tests driving a browser (see this module's docstring)."""

    @contextlib.contextmanager
    def browser(self, login='admin', path='/odoo'):
        """Open Odoo's test browser logged in as `login` (password: the login),
        on `path`. Set up like in ``HttpCase.browser_js``."""
        chrome = ChromeBrowser(self, headless=True, success_signal='__never__', debug=False)
        with self.allow_requests(browser=chrome), contextlib.ExitStack() as atexit:
            atexit.enter_context(flushing_cursor(self.cr))
            atexit.callback(self._wait_remaining_requests)
            atexit.enter_context(chrome.cleanup)
            if 'bus.bus' in self.env.registry:
                from odoo.addons.bus.websocket import WebsocketConnectionHandler  # noqa: PLC0415
                atexit.enter_context(patch.object(WebsocketConnectionHandler, 'websocket_allowed', return_value=True))
            self.authenticate(login, login, browser=chrome)
            browser = Browser(self, chrome)
            browser.goto(path)
            yield browser
            browser.check_errors()
