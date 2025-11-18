(function () {
  function initTagPicker(picker) {
    const searchInput = picker.querySelector("[data-tag-search]");
    const optionNodes = Array.from(picker.querySelectorAll("[data-tag-option]"));
    const groupNodes = Array.from(picker.querySelectorAll("[data-tag-group]"));
    const emptyState = picker.querySelector("[data-tag-empty-state]");
    const selectedBadge = picker.querySelector("[data-tag-selected-count]");

    const updateSelectedCount = () => {
      if (!selectedBadge) {
        return;
      }
      const checked = picker.querySelectorAll("[data-tag-option] input:checked").length;
      selectedBadge.textContent = `${checked} selected`;
    };

    const updateSearchResults = () => {
      const query = searchInput ? searchInput.value.trim().toLowerCase() : "";
      let visibleOptions = 0;

      optionNodes.forEach((node) => {
        const name = node.dataset.tagName || "";
        const matches = !query || name.includes(query);
        node.classList.toggle("d-none", !matches);
        if (matches) {
          visibleOptions += 1;
        }
      });

      groupNodes.forEach((group) => {
        const hasVisibleChild = group.querySelector("[data-tag-option]:not(.d-none)") !== null;
        group.classList.toggle("d-none", !hasVisibleChild);
      });

      if (emptyState) {
        emptyState.classList.toggle("d-none", visibleOptions > 0);
      }
    };

    if (searchInput) {
      searchInput.addEventListener("input", updateSearchResults);
    }

    picker.addEventListener("change", (event) => {
      if (event.target && event.target.closest("[data-tag-option]")) {
        updateSelectedCount();
      }
    });

    updateSearchResults();
    updateSelectedCount();
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-tag-picker]").forEach((picker) => {
      initTagPicker(picker);
    });
  });
})();
