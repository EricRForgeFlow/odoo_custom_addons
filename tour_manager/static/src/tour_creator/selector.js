/**
 * Selector computation adapted from web_tour's tour recorder
 * (web_tour/static/src/tour_recorder/tour_recorder.js), which does not export it.
 */
import { queryAll } from "@odoo/hoot-dom";

const PRECISE_IDENTIFIERS = ["data-menu-xmlid", "name", "contenteditable"];
const ODOO_CLASS_REGEX = /^oe?(-|_)[\w-]+$/;

/**
 * @param {string[]} paths
 * @returns {string}
 */
function reducePath(paths) {
    const numberOfElement = paths.length - 2;
    let currentElement = "";
    let hasReduced = false;
    let path = paths.shift();
    for (let i = 0; i < numberOfElement; i++) {
        currentElement = paths.shift();
        if (queryAll(`${path} ${paths.join(" > ")}`).length === 1) {
            hasReduced = true;
        } else {
            path += `${hasReduced ? " " : " > "}${currentElement}`;
            hasReduced = false;
        }
    }
    path += `${hasReduced ? " " : " > "}${paths.shift()}`;
    return path;
}

/**
 * Returns the shortest selector matching only `element`, built from its
 * Odoo classes and identifying attributes.
 *
 * @param {HTMLElement} element
 * @returns {string}
 */
export function getShortestSelector(element) {
    const paths = [];
    for (let el = element; el && el !== document.documentElement; el = el.parentElement) {
        paths.push(el);
    }
    paths.reverse();
    let filteredPath = [];
    let hasOdooClass = false;
    for (
        let currentElem = paths.pop();
        currentElem && (queryAll(filteredPath.join(" > ")).length !== 1 || !hasOdooClass);
        currentElem = paths.pop()
    ) {
        if (currentElem.parentElement.contentEditable === "true") {
            continue;
        }

        let currentPredicate = currentElem.tagName.toLowerCase();
        const odooClass = [...currentElem.classList].find((c) => c.match(ODOO_CLASS_REGEX));
        if (odooClass) {
            currentPredicate = `.${odooClass}`;
            hasOdooClass = true;
        }

        for (const identifier of PRECISE_IDENTIFIERS) {
            const identifierValue = currentElem.getAttribute(identifier);
            if (identifierValue) {
                currentPredicate += `[${identifier}='${CSS.escape(identifierValue)}']`;
            }
        }

        const siblingNodes = queryAll(":scope > " + currentPredicate, {
            root: currentElem.parentElement,
        });
        if (siblingNodes.length > 1) {
            currentPredicate += `:nth-child(${
                [...currentElem.parentElement.children].indexOf(currentElem) + 1
            })`;
        }

        filteredPath.unshift(currentPredicate);
    }

    if (filteredPath.length > 2) {
        return reducePath(filteredPath);
    }
    return filteredPath.join(" > ");
}

/**
 * @param {string} selector
 * @param {HTMLElement} element
 * @returns {boolean} whether `selector` matches `element` and nothing else
 */
export function isSelectorUnique(selector, element) {
    try {
        const matches = queryAll(selector);
        return matches.length === 1 && matches[0] === element;
    } catch {
        return false;
    }
}
