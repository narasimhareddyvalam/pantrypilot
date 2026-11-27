// PantryPilot phone page: it talks to the Flask API and switches between the
// Scan, Pantry and Assistant tabs. All text from the server or the user goes
// onto the page with textContent, never innerHTML, so nobody can inject HTML.

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

// Until Yuhao's pantry API and Sreeja's assistant API are ready, the page uses
// the sample data in sample_data.js. Set a switch to false when its API is ready.
const USE_SAMPLE_PANTRY = true;
const USE_SAMPLE_ASSISTANT = true;

// Phone photos are shrunk to this size before upload, so they send faster.
const MAX_PHOTO_SIZE = 1600;
const PHOTO_QUALITY = 0.85;

// How long to wait for the server before giving up (30 seconds).
const REQUEST_TIMEOUT_MS = 30000;

// Where the sample pantry is kept in this browser.
const SAMPLE_PANTRY_KEY = "pantrypilot.samplePantry";

// The words the page shows for each label type.
const LABEL_NAMES = {
  expiration: "Use by / Expires",
  best_before: "Best before",
  sell_by: "Sell by",
  manufacturing: "Made on",
  other: "Other date",
};

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

function $(id) {
  return document.getElementById(id);
}

// The error the page shows when the server can't be reached.
function makeNetworkError() {
  const error = new Error("We couldn't reach PantryPilot. Check your Wi-Fi and try again.");
  error.code = "network";
  return error;
}

// Send a request to our API and return its JSON answer.
// If something goes wrong, I throw an error with a sentence the user can read.
async function apiRequest(method, url, body) {
  const options = { method: method, headers: {} };
  if (body instanceof FormData) {
    options.body = body;
  } else if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  // If the server doesn't answer in time, I stop waiting, so the user gets the
  // Wi-Fi message and a Try again button instead of a screen that never changes.
  const controller = new AbortController();
  options.signal = controller.signal;
  const timer = setTimeout(function () {
    controller.abort();
  }, REQUEST_TIMEOUT_MS);

  try {
    let response;
    try {
      response = await fetch(url, options);
    } catch (networkProblem) {
      throw makeNetworkError();
    }

    let data = {};
    try {
      data = await response.json();
    } catch (notJson) {
      // If the answer stopped halfway because of the time limit, it counts as a lost connection.
      if (controller.signal.aborted) {
        throw makeNetworkError();
      }
      // Some errors don't come back as JSON, so I fall back to a plain sentence below.
    }

    if (!response.ok) {
      const error = new Error(data.error || "Something went wrong on our side. Please try again.");
      error.code = data.code || "server_error";
      throw error;
    }
    return data;
  } finally {
    // The answer came (or failed), so the timer isn't needed any more.
    clearTimeout(timer);
  }
}

// Show a short message at the bottom of the screen for 3 seconds.
let toastTimer = null;
function showToast(text) {
  const toast = $("toast");
  toast.textContent = text;
  toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(function () {
    toast.hidden = true;
  }, 3000);
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const TAB_NAMES = ["scan", "pantry", "assistant"];

// Show one tab's view, hide the other two, and mark which tab is active.
function showTab(name) {
  for (const tabName of TAB_NAMES) {
    const isActive = tabName === name;
    $("view-" + tabName).hidden = !isActive;
    if (isActive) {
      $("tab-" + tabName).setAttribute("aria-current", "page");
    } else {
      $("tab-" + tabName).removeAttribute("aria-current");
    }
  }
  window.scrollTo(0, 0);
}

// ---------------------------------------------------------------------------
// Start the page
// ---------------------------------------------------------------------------

function setUpPage() {
  for (const tabName of TAB_NAMES) {
    $("tab-" + tabName).addEventListener("click", function () {
      showTab(tabName);
    });
  }

  // The badges tell testers the page is showing sample data, not the real APIs.
  $("sample-badge-pantry").hidden = !USE_SAMPLE_PANTRY;
  $("sample-badge-assistant").hidden = !USE_SAMPLE_ASSISTANT;

  showTab("scan");
}

setUpPage();
