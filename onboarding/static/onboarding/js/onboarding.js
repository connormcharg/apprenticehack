/* ApprenticeHack — onboarding enhancements.
 *
 * Everything here is optional: without this file the page is still a working
 * form. Each blank is a real <input>, and the technologies blank accepts a
 * plain comma separated list ("Python, SQL, React").
 *
 * This script adds:
 *   1. a tag/chip editor over the technologies blank,
 *   2. blanks that grow to fit what you type, so the sentence never reflows
 *      awkwardly,
 *   3. quick-add suggestions for common technologies,
 *   4. error-summary links that focus the right blank.
 */
(function () {
  'use strict';

  /* These two run on every page, including the sign-in form, which has no
     [data-onboarding-form] wrapper. */

  /* -------------------------------------------------------- password reveal */

  Array.prototype.slice
    .call(document.querySelectorAll('[data-reveal]'))
    .forEach(function (button) {
      var input = document.getElementById(button.getAttribute('data-reveal'));
      if (!input) {
        return;
      }
      button.addEventListener('click', function () {
        var revealed = input.type === 'password';
        input.type = revealed ? 'text' : 'password';
        button.setAttribute('aria-pressed', String(revealed));
        button.setAttribute(
          'aria-label',
          revealed ? 'Hide password' : 'Show password'
        );
        input.focus();
      });
    });

  /* -------------------------------------------------------- error summary */

  Array.prototype.slice
    .call(document.querySelectorAll('[data-focus]'))
    .forEach(function (link) {
      link.addEventListener('click', function (event) {
        var target = document.getElementById(
          link.getAttribute('href').replace('#', '')
        );
        if (!target) {
          return;
        }
        event.preventDefault();

        // The technologies field is visually hidden once the chip editor is
        // active, so fall back to something the visitor can actually see.
        var focusTarget = target;
        if (target.offsetParent === null) {
          var parentBlank = target.closest('.blank');
          focusTarget =
            (parentBlank && parentBlank.querySelector('[data-tech-input]')) ||
            parentBlank ||
            target;
        }

        focusTarget.focus();
        focusTarget.scrollIntoView({ block: 'center', behavior: 'smooth' });
      });
    });

  var form = document.querySelector('[data-onboarding-form]');
  if (!form) {
    return;
  }

  var MAX_TECHNOLOGIES = 12;
  var MIN_BLANK_PX = 56;
  var WIDTH_BUFFER_PX = 8;
  // Mirrors OnboardingForm.TECHNOLOGY_SEPARATOR on the server.
  var SEPARATOR = /[,;\n]|\s+and\s+/i;

  /* ---------------------------------------------------------------- chips */

  var source = form.querySelector('[data-technologies-source]');
  var chipInput = null;
  var chips = [];
  // Assigned inside the chip-editor block below; the quick-add suggestions
  // need to reach it from outside, and strict-mode block scoping would
  // otherwise hide it.
  var addChips = function () {
    return false;
  };

  function splitTokens(value) {
    return String(value)
      .split(SEPARATOR)
      .map(function (part) {
        // Mirrors the server: trim, drop a trailing sentence full stop, trim
        // again. Leading dots are kept so ".NET" survives.
        return part.trim().replace(/\.+$/, '').trim();
      })
      .filter(Boolean);
  }

  function syncSource() {
    if (source) {
      source.value = chips.join(', ');
    }
  }

  function hasChip(name) {
    var needle = name.toLowerCase();
    return chips.some(function (chip) {
      return chip.toLowerCase() === needle;
    });
  }

  if (source) {
    var blank = source.closest('.blank');
    var sourceLabel = blank ? blank.querySelector('label') : null;

    var tokens = document.createElement('span');
    tokens.className = 'tokens';

    chipInput = document.createElement('input');
    chipInput.type = 'text';
    chipInput.className = 'tokens__input';
    chipInput.setAttribute('data-tech-input', '');
    chipInput.setAttribute('autocomplete', 'off');
    chipInput.setAttribute('autocapitalize', 'off');
    chipInput.setAttribute('spellcheck', 'false');
    chipInput.setAttribute(
      'aria-label',
      (sourceLabel ? sourceLabel.textContent.trim() : 'Technology') +
        ' — press Enter to add'
    );

    tokens.appendChild(chipInput);
    blank.appendChild(tokens);

    // The real field stays in the DOM (so it still submits) but steps out of
    // the way of the chip editor.
    source.classList.add('is-hidden');
    source.removeAttribute('data-autosize');
    source.setAttribute('tabindex', '-1');
    source.setAttribute('aria-hidden', 'true');

    if (source.getAttribute('aria-invalid') === 'true') {
      tokens.classList.add('tokens--invalid');
    }

    function renderChips() {
      Array.prototype.slice
        .call(tokens.querySelectorAll('.chip'))
        .forEach(function (node) {
          node.remove();
        });

      chips.forEach(function (name) {
        var chip = document.createElement('span');
        chip.className = 'chip';

        var label = document.createElement('span');
        label.className = 'chip__label';
        label.textContent = name;

        var remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'chip__remove';
        remove.textContent = '\u00d7';
        remove.setAttribute('aria-label', 'Remove ' + name);
        remove.addEventListener('click', function () {
          chips = chips.filter(function (existing) {
            return existing !== name;
          });
          renderChips();
          chipInput.focus();
        });

        chip.appendChild(label);
        chip.appendChild(remove);
        tokens.insertBefore(chip, chipInput);
      });

      chipInput.placeholder = chips.length ? 'add another' : 'Python, SQL';
      syncSource();
      refreshSuggestions();
    }

    addChips = function (raw) {
      var added = false;
      splitTokens(raw).forEach(function (name) {
        if (hasChip(name) || chips.length >= MAX_TECHNOLOGIES) {
          return;
        }
        chips.push(name);
        added = true;
      });
      if (added) {
        renderChips();
      }
      return added;
    };

    chipInput.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ',' || event.key === ';') {
        event.preventDefault();
        addChips(chipInput.value);
        chipInput.value = '';
        return;
      }
      if (event.key === 'Backspace' && chipInput.value === '' && chips.length) {
        event.preventDefault();
        chips.pop();
        renderChips();
      }
    });

    // Commit as soon as a separator is typed or pasted, keeping whatever
    // fragment is still being typed.
    chipInput.addEventListener('input', function () {
      var value = chipInput.value;
      var cut = Math.max(
        value.lastIndexOf(','),
        value.lastIndexOf(';'),
        value.lastIndexOf('\n')
      );
      if (cut === -1) {
        return;
      }
      addChips(value.slice(0, cut));
      chipInput.value = value.slice(cut + 1);
    });

    chipInput.addEventListener('blur', function () {
      if (chipInput.value.trim()) {
        addChips(chipInput.value);
        chipInput.value = '';
      }
    });

    tokens.addEventListener('click', function (event) {
      if (event.target === tokens) {
        chipInput.focus();
      }
    });

    form.addEventListener('submit', function () {
      if (chipInput.value.trim()) {
        addChips(chipInput.value);
        chipInput.value = '';
      }
      syncSource();
    });

    // Rebuild whatever the server rendered (a prefilled profile, or the raw
    // text of a submission that failed validation) as chips.
    splitTokens(source.value).forEach(function (name) {
      if (chips.length < MAX_TECHNOLOGIES && !hasChip(name)) {
        chips.push(name);
      }
    });
    renderChips();
  }

  /* ------------------------------------------------------------- autosize */

  var measurer = document.createElement('span');
  measurer.className = 'measure';
  measurer.setAttribute('aria-hidden', 'true');
  form.appendChild(measurer);

  function widthFor(input, text) {
    var style = window.getComputedStyle(input);

    measurer.style.fontFamily = style.fontFamily;
    measurer.style.fontSize = style.fontSize;
    measurer.style.fontWeight = style.fontWeight;
    measurer.style.fontStyle = style.fontStyle;
    measurer.style.letterSpacing = style.letterSpacing;
    measurer.style.textTransform = style.textTransform;
    measurer.textContent = text || '\u00a0';

    var chrome =
      parseFloat(style.paddingLeft) +
      parseFloat(style.paddingRight) +
      parseFloat(style.borderLeftWidth) +
      parseFloat(style.borderRightWidth);

    var width = measurer.getBoundingClientRect().width + chrome + WIDTH_BUFFER_PX;
    var min = parseFloat(style.minWidth);
    if (!isNaN(min)) {
      width = Math.max(width, min);
    }

    // Never wider than the form, so long values scroll inside the blank
    // instead of pushing the sentence off-screen.
    var max = Math.max(form.clientWidth - 4, MIN_BLANK_PX);
    return Math.round(Math.min(width, max));
  }

  var blanks = Array.prototype.slice.call(form.querySelectorAll('[data-autosize]'));

  function resizeBlank(input) {
    if (input.classList.contains('is-hidden')) {
      return;
    }
    input.style.width = widthFor(input, input.value || input.placeholder) + 'px';
  }

  blanks.forEach(function (input) {
    input.addEventListener('input', function () {
      resizeBlank(input);
    });
    resizeBlank(input);
  });

  var resizeQueued = false;
  window.addEventListener('resize', function () {
    if (resizeQueued) {
      return;
    }
    resizeQueued = true;
    window.requestAnimationFrame(function () {
      resizeQueued = false;
      blanks.forEach(resizeBlank);
    });
  });

  /* ---------------------------------------------------------- suggestions */

  var panel = form.querySelector('[data-suggestions-panel]');
  var list = form.querySelector('[data-suggestions-list]');
  var suggestions = (form.getAttribute('data-suggestions') || '')
    .split(',')
    .map(function (name) {
      return name.trim();
    })
    .filter(Boolean);

  function refreshSuggestions() {
    if (!panel) {
      return;
    }
    Array.prototype.slice
      .call(panel.querySelectorAll('.suggestion'))
      .forEach(function (button) {
        var present = hasChip(button.getAttribute('data-name'));
        button.disabled = present;
        button.classList.toggle('is-added', present);
      });
  }

  if (panel && list && chipInput && suggestions.length) {
    suggestions.forEach(function (name) {
      var button = document.createElement('button');
      button.type = 'button';
      button.className = 'suggestion';
      button.textContent = name;
      button.setAttribute('data-name', name);
      button.addEventListener('click', function () {
        addChips(name);
        chipInput.focus();
      });
      list.appendChild(button);
    });
    panel.hidden = false;
    refreshSuggestions();
  }

  /* ------------------------------------------------------------ autofocus */

  // Only on devices with a real keyboard: popping the on-screen keyboard up
  // on load is more annoying than helpful.
  var finePointer = window.matchMedia('(min-width: 48rem) and (pointer: fine)');
  if (finePointer.matches && !form.querySelector('[aria-invalid="true"]')) {
    var fillable = Array.prototype.slice.call(
      form.querySelectorAll('.blank__input:not(.is-hidden)')
    );
    var firstEmpty = fillable.filter(function (input) {
      return !input.value;
    })[0];
    if (firstEmpty) {
      firstEmpty.focus();
    }
  }
})();
