(function () {
  function initTagPicker(picker) {
    const searchInput = picker.querySelector("[data-tag-search]");
    const optionNodes = Array.from(picker.querySelectorAll("[data-tag-option]"));
    const groupNodes  = Array.from(picker.querySelectorAll("[data-tag-group]"));
    const emptyState  = picker.querySelector("[data-tag-empty-state]");
    const selectedBadge = picker.querySelector("[data-tag-selected-count]");

    const updateSelectedCount = () => {
      if (!selectedBadge) return;
      const checked = picker.querySelectorAll("[data-tag-option] input:checked").length;
      selectedBadge.textContent = `${checked} selected`;
    };

    const updateSearchResults = () => {
      const query    = searchInput ? searchInput.value.trim().toLowerCase() : "";
      const hasQuery = query.length > 0;
      let visibleOptions = 0;

      optionNodes.forEach((node) => {
        const name     = node.dataset.tagName   || "";
        const isHidden = node.dataset.tagHidden  === "true";
        const surfaced = node.dataset.tagSurfaced === "true";

        // A hidden tag is shown only when:
        //   • there is an active search query (so the user is looking for it), OR
        //   • auto-detection has surfaced it (keyword matched in dish/notes)
        const nameMatches = !hasQuery || name.includes(query);
        const show = nameMatches && (!isHidden || hasQuery || surfaced);

        node.classList.toggle("d-none", !show);
        if (show) visibleOptions += 1;
      });

      groupNodes.forEach((group) => {
        const hasVisible = group.querySelector("[data-tag-option]:not(.d-none)") !== null;
        group.classList.toggle("d-none", !hasVisible);
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

    // Expose so external scripts (e.g. auto-detection) can trigger a refresh
    // after surfacing or un-surfacing a hidden tag.
    picker._refreshTags = updateSearchResults;

    updateSearchResults();
    updateSelectedCount();
  }

  document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-tag-picker]").forEach((picker) => {
      initTagPicker(picker);
    });
  });
})();
