(() => {
  const root = document.querySelector('[data-asset-autocomplete]');
  if (!root) return;

  const input = root.querySelector('[role="combobox"]');
  const selectedId = root.querySelector('input[type="hidden"]');
  const menu = root.querySelector('[role="listbox"]');
  const searchUrl = root.dataset.searchUrl;
  let results = [];
  let activeIndex = -1;
  let debounceTimer;
  let requestController;

  const closeMenu = () => {
    menu.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
    activeIndex = -1;
  };

  const setActive = (index) => {
    const options = [...menu.querySelectorAll('[role="option"]')];
    if (!options.length) return;

    activeIndex = (index + options.length) % options.length;
    options.forEach((option, optionIndex) => {
      const isActive = optionIndex === activeIndex;
      option.classList.toggle('is-active', isActive);
      option.setAttribute('aria-selected', String(isActive));
    });
    const activeOption = options[activeIndex];
    input.setAttribute('aria-activedescendant', activeOption.id);
    activeOption.scrollIntoView({ block: 'nearest' });
  };

  const choose = (asset) => {
    input.value = asset.symbol;
    selectedId.value = asset.id;
    closeMenu();
    input.focus();
  };

  const render = (assets) => {
    results = assets;
    activeIndex = -1;
    menu.replaceChildren();

    if (!assets.length) {
      const empty = document.createElement('div');
      empty.className = 'tn-combobox-empty';
      empty.textContent = 'No se encontraron activos';
      menu.append(empty);
    } else {
      assets.forEach((asset, index) => {
        const option = document.createElement('button');
        option.type = 'button';
        option.id = `asset-option-${asset.id}`;
        option.className = 'tn-combobox-option';
        option.setAttribute('role', 'option');
        option.setAttribute('aria-selected', 'false');

        const symbol = document.createElement('span');
        symbol.className = 'tn-combobox-symbol';
        symbol.textContent = asset.symbol;

        const company = document.createElement('span');
        company.className = 'tn-combobox-company';
        const name = document.createElement('span');
        name.className = 'tn-combobox-name';
        name.textContent = asset.name;
        company.append(name);

        const market = document.createElement('span');
        market.className = 'tn-combobox-market';
        market.textContent = `${asset.exchange} · ${asset.currency}`;

        option.append(symbol, company, market);
        option.addEventListener('pointerdown', (event) => event.preventDefault());
        option.addEventListener('click', () => choose(asset));
        option.addEventListener('mousemove', () => setActive(index));
        menu.append(option);
      });
    }

    menu.hidden = false;
    input.setAttribute('aria-expanded', 'true');
  };

  const search = async () => {
    const query = input.value.trim();
    if (!query) {
      closeMenu();
      return;
    }

    requestController?.abort();
    requestController = new AbortController();
    try {
      const response = await fetch(`${searchUrl}?q=${encodeURIComponent(query)}`, {
        headers: { Accept: 'application/json' },
        signal: requestController.signal,
      });
      if (!response.ok) throw new Error(`Asset search failed: ${response.status}`);
      const payload = await response.json();
      render(payload.assets || []);
    } catch (error) {
      if (error.name !== 'AbortError') closeMenu();
    }
  };

  input.addEventListener('input', () => {
    selectedId.value = '';
    window.clearTimeout(debounceTimer);
    debounceTimer = window.setTimeout(search, 160);
  });

  input.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      if (menu.hidden) search();
      else setActive(activeIndex + 1);
    } else if (event.key === 'ArrowUp' && !menu.hidden) {
      event.preventDefault();
      setActive(activeIndex - 1);
    } else if (event.key === 'Enter' && !menu.hidden && activeIndex >= 0) {
      event.preventDefault();
      choose(results[activeIndex]);
    } else if (event.key === 'Escape') {
      closeMenu();
    }
  });

  input.addEventListener('focus', () => {
    if (input.value.trim() && !selectedId.value) search();
  });

  document.addEventListener('pointerdown', (event) => {
    if (!root.contains(event.target)) closeMenu();
  });
})();
