"use strict";

for (const button of document.querySelectorAll("[data-copy]")) {
  const label = button.getAttribute("aria-label");
  button.addEventListener("click", async () => {
    const code = document.getElementById(button.dataset.copy);
    const status = document.getElementById("copy-status");
    try {
      await navigator.clipboard.writeText(code.textContent);
      button.classList.add("copied");
      button.setAttribute("aria-label", "Command copied");
      status.textContent = "Command copied to clipboard.";
      setTimeout(() => {
        button.classList.remove("copied");
        button.setAttribute("aria-label", label);
        status.textContent = "";
      }, 2000);
    } catch {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(code);
      selection.removeAllRanges();
      selection.addRange(range);
      status.textContent = "Command selected. Copy it with your keyboard.";
    }
  });
}
