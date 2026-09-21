"use strict";

const installers = {
  mac: {
    command: "curl -fsSL https://aurkakoak.github.io/cadkit/install.sh | sh",
    note: "Run in Terminal.",
  },
  windows: {
    command: "irm https://aurkakoak.github.io/cadkit/install.ps1 | iex",
    note: "Run in PowerShell.",
  },
};

for (const button of document.querySelectorAll("[data-platform]")) {
  button.addEventListener("click", () => {
    const selected = installers[button.dataset.platform];
    document.getElementById("install-command").textContent = selected.command;
    document.getElementById("platform-note").textContent = selected.note;
    for (const platform of document.querySelectorAll("[data-platform]")) {
      platform.setAttribute("aria-pressed", String(platform === button));
    }
  });
}

for (const button of document.querySelectorAll("[data-copy]")) {
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
        button.setAttribute("aria-label", button.dataset.copy === "skill-command" ? "Copy skill command" : "Copy installer command");
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
