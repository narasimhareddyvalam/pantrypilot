// PantryPilot phone page: it talks to the Flask API and switches between the
// Scan, Pantry and Assistant tabs. All text from the server or the user goes
// onto the page with textContent, never innerHTML, so nobody can inject HTML.

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

// Until the pantry API and the assistant API are ready, the page uses
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

// Send a request to the app's API and return its JSON answer.
// If something goes wrong, it throws an error with a sentence the user can read.
async function apiRequest(method, url, body) {
  const options = { method: method, headers: {} };
  if (body instanceof FormData) {
    options.body = body;
  } else if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  // If the server doesn't answer in time, the page stops waiting, so the user gets the
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
      // Some errors don't come back as JSON, so the plain sentence below is used instead.
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

  // The pantry may have changed on another tab, so it is loaded fresh every time.
  if (name === "pantry") {
    refreshPantry();
  }
}

// ---------------------------------------------------------------------------
// Dates
// ---------------------------------------------------------------------------

const DATE_PATTERN = /^\d{4}-\d{2}-\d{2}$/;
const ONE_DAY = 24 * 60 * 60 * 1000;

// Turn "2027-01-05" into a Date at midnight on that day, in this phone's time zone.
// It is built from the three parts on purpose: new Date("2027-01-05") is read as
// UTC, and in the US that would show the day before.
function parseDate(text) {
  if (!text || !DATE_PATTERN.test(text)) {
    return null;
  }
  const parts = text.split("-");
  const year = Number(parts[0]);
  const month = Number(parts[1]);
  const day = Number(parts[2]);
  const date = new Date(year, month - 1, day);
  // A date like 2027-02-30 rolls over into March, so the check makes sure it stayed the same day.
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
    return null;
  }
  return date;
}

// "2027-01-05" becomes "Jan 5, 2027". A missing date becomes "No date".
function formatDate(text) {
  const date = parseDate(text);
  if (date === null) {
    return "No date";
  }
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

// How many days from today until the date. A negative number means it has passed.
function daysFromToday(text) {
  const date = parseDate(text);
  if (date === null) {
    return null;
  }
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  // Math.round also covers the days when the clocks change by one hour.
  return Math.round((date - today) / ONE_DAY);
}

// Turn a number of days into words, like "In 3 days" or "Yesterday".
function describeDays(days) {
  if (days === null) {
    return "";
  }
  if (days === 0) {
    return "Today";
  }
  if (days === 1) {
    return "Tomorrow";
  }
  if (days === -1) {
    return "Yesterday";
  }
  if (days > 1) {
    return "In " + days + " days";
  }
  return -days + " days ago";
}

// ---------------------------------------------------------------------------
// Item forms (the scan review form and the edit form use the same fields)
// ---------------------------------------------------------------------------

// Read a product form and return a clean item.
// If something is missing or wrong, it throws an error with a sentence to show.
function readItemForm(form) {
  const productName = form.elements.productName.value.trim();
  const labelType = form.elements.labelType.value;
  const date = form.elements.date.value.trim();

  if (productName === "") {
    throw new Error("Please add the product name.");
  }
  if (productName.length > 80) {
    throw new Error("The product name can be at most 80 characters.");
  }
  // On a laptop, the date box can hold a half-typed date (like 01/05/yyyy). Its value
  // is then empty, so that is checked first, instead of saving "no date" by mistake.
  if (form.elements.date.validity.badInput) {
    throw new Error("Please finish the date, or clear it if the package has no date.");
  }
  if (date !== "" && parseDate(date) === null) {
    throw new Error("Date must look like 2027-01-05.");
  }

  // An empty label or date means "unknown", which the pantry stores as null.
  let cleanLabel = labelType;
  if (cleanLabel === "") {
    cleanLabel = null;
  }
  let cleanDate = date;
  if (cleanDate === "") {
    cleanDate = null;
  }
  return { productName: productName, labelType: cleanLabel, date: cleanDate };
}

// Put an item's details into a product form.
function fillItemForm(form, item) {
  form.elements.productName.value = item.productName || "";
  form.elements.labelType.value = item.labelType || "";
  form.elements.date.value = item.date || "";
}

// Show an error sentence under a form.
function showFormError(elementId, message) {
  const box = $(elementId);
  box.textContent = message;
  box.hidden = false;
}

// ---------------------------------------------------------------------------
// Pantry storage: the sample list in this browser, or the pantry API
// ---------------------------------------------------------------------------

const ITEM_FIELDS = ["productName", "labelType", "date"];

// If the browser blocks storage (for example in private browsing), the list
// is kept in memory instead, so the page still works until it is closed.
let memoryPantry = null;
let storageBlocked = false;

// Make a separate copy of a list of items, so changing one never changes the other.
function copyItems(items) {
  return JSON.parse(JSON.stringify(items));
}

function readSampleItems() {
  let saved = null;
  try {
    saved = localStorage.getItem(SAMPLE_PANTRY_KEY);
  } catch (problem) {
    storageBlocked = true;
  }
  if (saved !== null) {
    try {
      return JSON.parse(saved);
    } catch (brokenData) {
      // The saved list is broken, so the page starts again from the sample items below.
    }
  }
  if (memoryPantry === null) {
    memoryPantry = copyItems(SAMPLE_PANTRY);
  }
  return memoryPantry;
}

function writeSampleItems(items) {
  memoryPantry = items;
  try {
    localStorage.setItem(SAMPLE_PANTRY_KEY, JSON.stringify(items));
  } catch (problem) {
    storageBlocked = true;
  }
}

// Get every pantry item.
async function loadPantry() {
  if (USE_SAMPLE_PANTRY) {
    return copyItems(readSampleItems());
  }
  return await apiRequest("GET", "/pantry/items");
}

// Save a new item and return it with the id it was given.
async function addPantryItem(item) {
  if (USE_SAMPLE_PANTRY) {
    const items = readSampleItems();
    // A new item gets the next id after the highest one, like a database would give.
    let nextId = 1;
    for (const existing of items) {
      if (existing.id >= nextId) {
        nextId = existing.id + 1;
      }
    }
    const saved = { id: nextId, productName: item.productName, labelType: item.labelType, date: item.date };
    items.push(saved);
    writeSampleItems(items);
    return copyItems(saved);
  }
  return await apiRequest("POST", "/pantry/items", item);
}

// Change some fields of one item and return the updated item.
async function updatePantryItem(id, changes) {
  if (USE_SAMPLE_PANTRY) {
    const items = readSampleItems();
    for (const item of items) {
      if (item.id === id) {
        // Only the fields that were sent change, the same way PATCH works.
        for (const field of ITEM_FIELDS) {
          if (field in changes) {
            item[field] = changes[field];
          }
        }
        writeSampleItems(items);
        return copyItems(item);
      }
    }
    const error = new Error("That item isn't in your pantry anymore.");
    error.code = "not_found";
    throw error;
  }
  return await apiRequest("PATCH", "/pantry/items/" + id, changes);
}

// Remove one item from the pantry.
async function deletePantryItem(id) {
  if (USE_SAMPLE_PANTRY) {
    const kept = [];
    for (const item of readSampleItems()) {
      if (item.id !== id) {
        kept.push(item);
      }
    }
    writeSampleItems(kept);
    return;
  }
  await apiRequest("DELETE", "/pantry/items/" + id);
}

// ---------------------------------------------------------------------------
// Scan tab
// ---------------------------------------------------------------------------

let currentPhoto = null;   // the shrunk photo, kept so Try again can send it again
let previewUrl = null;     // the address of the preview picture in this browser
let scanBusy = false;      // true while a photo is being read, so a second tap does nothing
let saveBusy = false;      // true while an item is being saved, for the same reason

// The page passes ?sample=... from its own address on to the scan, so testers
// can see the other example results, for example /?sample=ambiguous.
function sampleQuery() {
  const sample = new URLSearchParams(window.location.search).get("sample");
  if (sample) {
    return "?sample=" + encodeURIComponent(sample);
  }
  return "";
}

// Show one step of the Scan tab: "start", "preview" or "review".
function showScanStep(step) {
  $("scan-start").hidden = step !== "start";
  $("scan-preview").hidden = step !== "preview";
  $("review-form").hidden = step !== "review";
  $("scan-error").hidden = true;
}

// Make a phone photo smaller before sending it. Big photos are slow to send,
// and drawing the photo onto a canvas also turns iPhone HEIC photos into JPEG.
function shrinkPhoto(file) {
  return new Promise(function (resolve) {
    const fileUrl = URL.createObjectURL(file);
    const picture = new Image();

    picture.onload = function () {
      let width = picture.naturalWidth;
      let height = picture.naturalHeight;
      const longestSide = Math.max(width, height);
      if (longestSide > MAX_PHOTO_SIZE) {
        const scale = MAX_PHOTO_SIZE / longestSide;
        width = Math.round(width * scale);
        height = Math.round(height * scale);
      }
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      canvas.getContext("2d").drawImage(picture, 0, 0, width, height);
      URL.revokeObjectURL(fileUrl);
      canvas.toBlob(function (blob) {
        // If the browser can't make a JPEG, the original file is sent instead.
        resolve(blob || file);
      }, "image/jpeg", PHOTO_QUALITY);
    };

    picture.onerror = function () {
      // This browser can't open the photo (for example HEIC on some laptops),
      // so the original file is sent and the server answers.
      URL.revokeObjectURL(fileUrl);
      resolve(file);
    };

    picture.src = fileUrl;
  });
}

// Show the chosen photo, so the user can check it before reading the date.
async function choosePhoto(file) {
  if (!file) {
    return;
  }
  currentPhoto = await shrinkPhoto(file);
  if (previewUrl !== null) {
    URL.revokeObjectURL(previewUrl);
  }
  previewUrl = URL.createObjectURL(currentPhoto);
  $("preview-image").src = previewUrl;
  showScanStep("preview");
  // The buttons the user just used are now hidden, so the focus moves to the next step.
  $("read-date").focus();
}

// Send the photo to the server and show what it read.
async function readDate() {
  // A second tap while the first one is still working does nothing.
  if (scanBusy || currentPhoto === null) {
    return;
  }
  scanBusy = true;
  $("scan-error").hidden = true;
  $("preview-actions").hidden = true;
  $("scan-loading").hidden = false;
  $("photo-frame").classList.add("is-reading");

  let result = null;
  let problem = null;
  try {
    const form = new FormData();
    form.append("image", currentPhoto, "photo.jpg");
    result = await apiRequest("POST", "/scans" + sampleQuery(), form);
  } catch (error) {
    problem = error;
  }

  // The waiting is over, so the buttons come back first.
  scanBusy = false;
  $("scan-loading").hidden = true;
  $("preview-actions").hidden = false;
  $("photo-frame").classList.remove("is-reading");

  if (problem !== null) {
    $("scan-error-text").textContent = problem.message;
    $("scan-error").hidden = false;
    // On a small screen the message can end up below the tab bar, so it is scrolled into view.
    $("scan-error").scrollIntoView({ block: "nearest" });
    return;
  }
  showReview(result);
}

// Fill the review form with what the server read, so the user can check it.
function showReview(result) {
  const rawText = result.rawText || "";
  const form = $("review-form");
  form.reset();
  fillItemForm(form, { productName: "", labelType: result.labelType, date: result.date });
  $("review-title").textContent = "Check what we read";

  // The photo stays in view, so the person can check the text against it.
  if (previewUrl !== null) {
    $("review-photo").src = previewUrl;
    $("review-photo").hidden = false;
  } else {
    $("review-photo").hidden = true;
  }

  $("raw-text").textContent = rawText;
  // When nothing was read, there is nothing to show in the "We read" box.
  $("raw-text-box").hidden = rawText === "";

  const notice = $("review-notice");
  if (result.requiresReview) {
    if (rawText === "") {
      notice.textContent = "We couldn't read the label. Type the details yourself or retake the photo.";
    } else {
      notice.textContent = "Please check this. We weren't sure about everything we read.";
    }
    notice.hidden = false;
  } else {
    notice.hidden = true;
  }

  $("review-error").hidden = true;
  $("review-retake").textContent = "Retake";
  showScanStep("review");
  // The focus moves to the new step, so a screen reader reads it out.
  $("review-title").focus();
}

// Let the user type the details in, without a photo.
function startManualEntry() {
  const form = $("review-form");
  form.reset();
  fillItemForm(form, { productName: "", labelType: null, date: null });
  $("review-title").textContent = "Type in the details";
  // There is no photo when the details are typed in.
  $("review-photo").hidden = true;
  $("raw-text-box").hidden = true;
  $("review-notice").hidden = true;
  $("review-error").hidden = true;
  // No photo was taken, so the button that goes back says Cancel, not Retake.
  $("review-retake").textContent = "Cancel";
  showScanStep("review");
  $("review-title").focus();
}

// Save the checked item to the pantry.
async function saveScannedItem(event) {
  event.preventDefault();
  if (saveBusy) {
    return;
  }

  let item;
  try {
    item = readItemForm($("review-form"));
  } catch (problem) {
    showFormError("review-error", problem.message);
    return;
  }

  saveBusy = true;
  $("save-item").disabled = true;
  try {
    const saved = await addPantryItem(item);
    showToast("Saved " + saved.productName + " to your pantry.");
    resetScan();
    // The form is gone, so the focus goes back to the first button of the Scan tab.
    $("take-photo-button").focus();
  } catch (error) {
    showFormError("review-error", error.message);
  } finally {
    saveBusy = false;
    $("save-item").disabled = false;
  }
}

// Go back to the start of the Scan tab.
function resetScan() {
  currentPhoto = null;
  // Clearing the inputs lets the user pick the same photo again if they want.
  $("photo-take").value = "";
  $("photo-choose").value = "";
  $("review-form").reset();
  showScanStep("start");
}

// ---------------------------------------------------------------------------
// Pantry tab
// ---------------------------------------------------------------------------

let editingId = null;   // the id of the item open in the edit dialog
let editBusy = false;   // true while an edit is being saved

// Sort by date, soonest first. Items without a date go last, and items with
// the same date are sorted by name.
function sortItems(items) {
  const sorted = items.slice();
  sorted.sort(function (first, second) {
    if (first.date === second.date) {
      return first.productName.localeCompare(second.productName, "en", { sensitivity: "base" });
    }
    if (first.date === null) {
      return 1;
    }
    if (second.date === null) {
      return -1;
    }
    // Dates written as YYYY-MM-DD sort correctly as plain text.
    if (first.date < second.date) {
      return -1;
    }
    return 1;
  });
  return sorted;
}

// Make a small page element with a class and some text.
// Only textContent is used, so a name like "<b>Oats</b>" shows as plain text.
function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  element.className = className;
  element.textContent = text;
  return element;
}

// Build one row of the pantry list.
function makeItemRow(item) {
  const row = makeElement("li", "item", "");

  // Left side: the product name and its label badge.
  const about = makeElement("div", "item-about", "");
  about.appendChild(makeElement("p", "item-name", item.productName));
  if (item.labelType && LABEL_NAMES[item.labelType]) {
    about.appendChild(makeElement("span", "badge badge-" + item.labelType, LABEL_NAMES[item.labelType]));
  } else {
    about.appendChild(makeElement("span", "badge badge-none", "No label type"));
  }

  // Right side: the printed date, and how far away it is.
  const when = makeElement("div", "item-date", "");
  if (parseDate(item.date) === null) {
    when.appendChild(makeElement("span", "no-date", "No date"));
  } else {
    when.appendChild(makeElement("span", "stamp", formatDate(item.date)));
  }
  when.appendChild(makeElement("span", "item-when", describeDays(daysFromToday(item.date))));

  // Bottom: Edit and Delete. The longer names help people who use a screen reader.
  const actions = makeElement("div", "item-actions", "");
  const editButton = makeElement("button", "edit-button", "Edit");
  editButton.type = "button";
  editButton.setAttribute("aria-label", "Edit " + item.productName);
  editButton.addEventListener("click", function () {
    openEditDialog(item);
  });
  const deleteButton = makeElement("button", "delete-button", "Delete");
  deleteButton.type = "button";
  deleteButton.setAttribute("aria-label", "Delete " + item.productName);
  deleteButton.addEventListener("click", function () {
    confirmDelete(item);
  });
  actions.appendChild(editButton);
  actions.appendChild(deleteButton);

  row.appendChild(about);
  row.appendChild(when);
  row.appendChild(actions);
  return row;
}

// Draw the whole pantry list.
function renderPantry(items) {
  const list = $("pantry-list");
  list.textContent = "";
  for (const item of sortItems(items)) {
    list.appendChild(makeItemRow(item));
  }
  $("pantry-empty").hidden = items.length > 0;
  // If the browser blocks storage, a notice warns that the list won't be kept.
  $("storage-notice").hidden = !(USE_SAMPLE_PANTRY && storageBlocked);
}

// Load the pantry again and draw it, or show what went wrong.
async function refreshPantry() {
  $("pantry-error").hidden = true;
  try {
    const items = await loadPantry();
    renderPantry(items);
  } catch (error) {
    $("pantry-error-text").textContent = error.message;
    $("pantry-error").hidden = false;
  }
}

// After the list is drawn again, put the focus back on one item's Edit button,
// so a keyboard user doesn't lose their place. If it isn't there, use the heading.
function focusEditButton(productName) {
  for (const button of document.querySelectorAll("#pantry-list .edit-button")) {
    if (button.getAttribute("aria-label") === "Edit " + productName) {
      button.focus();
      return;
    }
  }
  $("pantry-title").focus();
}

// Open the edit dialog with one item's details in it.
function openEditDialog(item) {
  editingId = item.id;
  fillItemForm($("edit-form"), item);
  $("edit-error").hidden = true;
  $("edit-dialog").showModal();
}

// Save the changes from the edit dialog.
async function saveEditedItem(event) {
  event.preventDefault();
  if (editBusy) {
    return;
  }

  let changes;
  try {
    changes = readItemForm($("edit-form"));
  } catch (problem) {
    showFormError("edit-error", problem.message);
    return;
  }

  editBusy = true;
  try {
    await updatePantryItem(editingId, changes);
    $("edit-dialog").close();
    showToast("Saved changes to " + changes.productName + ".");
    await refreshPantry();
    focusEditButton(changes.productName);
  } catch (error) {
    showFormError("edit-error", error.message);
  } finally {
    editBusy = false;
  }
}

// Delete one item, after the user says yes.
async function confirmDelete(item) {
  // The browser asks first, so one wrong tap can't delete anything.
  if (!window.confirm("Delete " + item.productName + " from your pantry?")) {
    return;
  }
  try {
    await deletePantryItem(item.id);
    showToast("Deleted " + item.productName + ".");
    await refreshPantry();
    // The row is gone, so the focus goes to the pantry heading.
    $("pantry-title").focus();
  } catch (error) {
    $("pantry-error-text").textContent = error.message;
    $("pantry-error").hidden = false;
  }
}

// ---------------------------------------------------------------------------
// Assistant tab
// ---------------------------------------------------------------------------

// How the sample assistant says each label in a sentence.
const LABEL_PHRASES = {
  expiration: "use by",
  best_before: "best before",
  sell_by: "sell by",
  manufacturing: "made on",
};

let askBusy = false;          // true while a question is being answered
let offlineTriesLeft = 0;     // only for /?assistant=offline, to test the error and Try again

// Find the words in a piece of text, in lower case: "My oats?" gives ["my", "oats"].
function wordsIn(text) {
  return text.toLowerCase().match(/[a-z]+/g) || [];
}

// The sample assistant's answer about one pantry item.
function answerAboutItem(item) {
  if (parseDate(item.date) === null) {
    return "Your " + item.productName + " was saved without a date, so I don't know it. You can add it from the Pantry tab.";
  }
  const phrase = LABEL_PHRASES[item.labelType];
  if (phrase) {
    return "The label on your " + item.productName + " says " + phrase + " " + formatDate(item.date) + ".";
  }
  return "The label on your " + item.productName + " shows " + formatDate(item.date) + ".";
}

// The sample assistant: it answers from the pantry list and the sample answers.
function sampleAnswer(question, items) {
  const questionWords = wordsIn(question);

  // Step 1: if the question names something in the pantry (any word of 3 or
  // more letters from its name, like "oats"), the answer is about that item.
  for (const item of items) {
    for (const word of wordsIn(item.productName)) {
      if (word.length >= 3 && questionWords.includes(word)) {
        return answerAboutItem(item);
      }
    }
  }

  // Step 2: otherwise, a label word in the question gets explained.
  const lowerQuestion = question.toLowerCase();
  if (lowerQuestion.includes("best before")) {
    return SAMPLE_ANSWERS.best_before;
  }
  if (lowerQuestion.includes("use by") || lowerQuestion.includes("expire") || lowerQuestion.includes("expiration")) {
    return SAMPLE_ANSWERS.expiration;
  }
  if (lowerQuestion.includes("sell by")) {
    return SAMPLE_ANSWERS.sell_by;
  }
  if (lowerQuestion.includes("made on") || lowerQuestion.includes("manufactur") || lowerQuestion.includes("mfg")) {
    return SAMPLE_ANSWERS.manufacturing;
  }
  return SAMPLE_ANSWERS.fallback;
}

// Get an answer from the sample assistant, or from the assistant API.
async function askAssistant(question) {
  if (USE_SAMPLE_ASSISTANT) {
    if (offlineTriesLeft > 0) {
      offlineTriesLeft = offlineTriesLeft - 1;
      const error = new Error("The assistant isn't available right now.");
      error.code = "try_again";
      throw error;
    }
    const items = await loadPantry();
    return sampleAnswer(question, items);
  }
  // The pantry list goes with the question, so the assistant can answer about
  // saved items wherever the pantry is kept (on this phone, or in the pantry API).
  const items = await loadPantry();
  const data = await apiRequest("POST", "/assistant", { question: question, items: items });
  return data.answer;
}

// Add a chat bubble. role is "user" or "assistant".
function addBubble(role, text) {
  const bubble = makeElement("p", "bubble bubble-" + role, text);
  $("chat").appendChild(bubble);
  bubble.scrollIntoView({ block: "nearest" });
  return bubble;
}

// Add a bubble that says what went wrong, with a Try again button.
function addErrorBubble(message, question) {
  const bubble = makeElement("div", "bubble bubble-error", "");
  bubble.appendChild(makeElement("span", "", message));
  const retry = makeElement("button", "", "Try again");
  retry.type = "button";
  retry.addEventListener("click", function () {
    bubble.remove();
    sendQuestion(question, true);
  });
  bubble.appendChild(retry);
  $("chat").appendChild(bubble);
  bubble.scrollIntoView({ block: "nearest" });
}

// The Ask button only works when there is a question and nothing else is running.
function updateSendButton() {
  $("ask-send").disabled = askBusy || $("question").value.trim() === "";
}

// Ask one question and show the answer. On Try again, isRetry is true,
// so the question is not shown a second time.
async function sendQuestion(question, isRetry) {
  const cleanQuestion = question.trim();
  if (askBusy || cleanQuestion === "") {
    return;
  }
  askBusy = true;
  updateSendButton();
  if (!isRetry) {
    addBubble("user", cleanQuestion);
  }
  const thinking = addBubble("assistant", "Thinking…");
  thinking.classList.add("bubble-thinking");

  try {
    const answer = await askAssistant(cleanQuestion);
    thinking.remove();
    addBubble("assistant", answer);
  } catch (error) {
    thinking.remove();
    addErrorBubble(error.message, cleanQuestion);
  } finally {
    askBusy = false;
    updateSendButton();
  }
}

// Send what the user typed in the question box.
function submitQuestion(event) {
  event.preventDefault();
  const question = $("question").value;
  if (askBusy || question.trim() === "") {
    return;
  }
  $("question").value = "";
  sendQuestion(question, false);
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

  // Scan tab: the two buttons open the hidden photo inputs.
  $("take-photo-button").addEventListener("click", function () {
    $("photo-take").click();
  });
  $("choose-photo-button").addEventListener("click", function () {
    $("photo-choose").click();
  });
  $("photo-take").addEventListener("change", function (event) {
    choosePhoto(event.target.files[0]);
  });
  $("photo-choose").addEventListener("change", function (event) {
    choosePhoto(event.target.files[0]);
  });
  $("manual-entry").addEventListener("click", startManualEntry);
  $("read-date").addEventListener("click", readDate);
  $("scan-retry").addEventListener("click", readDate);
  $("retake").addEventListener("click", resetScan);
  $("review-retake").addEventListener("click", resetScan);
  $("review-form").addEventListener("submit", saveScannedItem);

  // Pantry tab
  $("edit-form").addEventListener("submit", saveEditedItem);
  $("edit-cancel").addEventListener("click", function () {
    $("edit-dialog").close();
  });
  $("go-scan").addEventListener("click", function () {
    showTab("scan");
  });
  $("pantry-retry").addEventListener("click", refreshPantry);

  // Assistant tab
  $("ask-form").addEventListener("submit", submitQuestion);
  $("question").addEventListener("input", updateSendButton);
  for (const chip of document.querySelectorAll("#suggestions .chip")) {
    chip.addEventListener("click", function () {
      sendQuestion(chip.textContent, false);
    });
  }
  // /?assistant=offline makes the first question fail, so testers can see
  // the error and Try again before the real assistant is connected.
  if (new URLSearchParams(window.location.search).get("assistant") === "offline") {
    offlineTriesLeft = 1;
  }

  // The badges show while a switch is on: the pantry is saved on this phone,
  // and the assistant gives sample answers instead of using the real API.
  $("sample-badge-pantry").hidden = !USE_SAMPLE_PANTRY;
  $("sample-badge-assistant").hidden = !USE_SAMPLE_ASSISTANT;

  showTab("scan");
}

setUpPage();
