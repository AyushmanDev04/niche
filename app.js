const state = {
  apiBase: localStorage.getItem("niche.apiBase") || "http://localhost:5000",
  accessToken: localStorage.getItem("niche.accessToken") || "",
  refreshToken: localStorage.getItem("niche.refreshToken") || "",
  stores: [],
  items: [],
  tags: [],
  reviews: [],
};

const els = {
  apiBase: document.querySelector("#apiBase"),
  saveApiBase: document.querySelector("#saveApiBase"),
  connectionState: document.querySelector("#connectionState"),
  authState: document.querySelector("#authState"),
  authMetric: document.querySelector("#authMetric"),
  alertRegion: document.querySelector("#alertRegion"),
  viewTitle: document.querySelector("#viewTitle"),
  refreshData: document.querySelector("#refreshData"),
  storeCount: document.querySelector("#storeCount"),
  itemCount: document.querySelector("#itemCount"),
  tagCount: document.querySelector("#tagCount"),
  recentItems: document.querySelector("#recentItems"),
  storesTable: document.querySelector("#storesTable"),
  itemsTable: document.querySelector("#itemsTable"),
  tagsTable: document.querySelector("#tagsTable"),
  reviewsTable: document.querySelector("#reviewsTable"),
  loginForm: document.querySelector("#loginForm"),
  registerForm: document.querySelector("#registerForm"),
  storeForm: document.querySelector("#storeForm"),
  itemForm: document.querySelector("#itemForm"),
  tagForm: document.querySelector("#tagForm"),
  linkTagForm: document.querySelector("#linkTagForm"),
  reviewForm: document.querySelector("#reviewForm"),
  logoutButton: document.querySelector("#logoutButton"),
  checkApiButton: document.querySelector("#checkApiButton"),
  apiCheckResult: document.querySelector("#apiCheckResult"),
  menuToggle: document.querySelector("#menuToggle"),
  sidebarScrim: document.querySelector("#sidebarScrim"),
  itemSubmit: document.querySelector("#itemForm button[type='submit']"),
  tagSubmit: document.querySelector("#tagForm button[type='submit']"),
  linkTagSubmit: document.querySelector("#linkTagForm button[type='submit']"),
  reviewSubmit: document.querySelector("#reviewForm button[type='submit']"),
};

els.apiBase.value = state.apiBase;

function setAlert(message, type = "info") {
  els.alertRegion.innerHTML = "";
  if (!message) return;

  const alert = document.createElement("div");
  alert.className = `alert ${type}`;
  alert.textContent = message;
  els.alertRegion.append(alert);
}

function apiUrl(path) {
  return `${state.apiBase.replace(/\/$/, "")}${path}`;
}

async function request(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (state.accessToken) {
    headers.Authorization = `Bearer ${state.accessToken}`;
  }

  const response = await fetch(apiUrl(path), {
    ...options,
    headers,
  });

  let body = null;
  const text = await response.text();
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { message: text };
    }
  }

  if (!response.ok) {
    const message = body?.message || body?.description || `Request failed with ${response.status}`;
    throw new Error(message);
  }

  return body;
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function updateAuthUi() {
  const signedIn = Boolean(state.accessToken);
  els.authState.textContent = signedIn ? "Signed in" : "Signed out";
  els.authState.classList.toggle("muted", !signedIn);
  els.authMetric.textContent = signedIn ? "Token ready" : "No token";
}

function setMenuOpen(isOpen) {
  document.body.classList.toggle("nav-open", isOpen);
  els.menuToggle.setAttribute("aria-expanded", String(isOpen));
}

function setView(viewName) {
  const knownView = document.querySelector(`[data-view="${viewName}"]`) ? viewName : "dashboard";

  document.querySelectorAll("[data-view]").forEach((view) => {
    view.classList.toggle("active", view.dataset.view === knownView);
  });

  document.querySelectorAll("[data-view-link]").forEach((link) => {
    link.classList.toggle("active", link.dataset.viewLink === knownView);
  });

  els.viewTitle.textContent = knownView.charAt(0).toUpperCase() + knownView.slice(1);
  setMenuOpen(false);
}

function renderTable(target, columns, rows) {
  if (!rows.length) {
    target.className = "data-table empty-state";
    target.textContent = "No records loaded.";
    return;
  }

  target.className = "data-table";
  const head = columns.map((column) => `<th>${column.label}</th>`).join("");
  const body = rows
    .map((row) => {
      const cells = columns.map((column) => `<td>${column.value(row)}</td>`).join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");

  target.innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function optionLabel(record, fallback) {
  return record?.name || `${fallback} #${record?.id}`;
}

function populateSelect(select, rows, fallback) {
  select.innerHTML = "";
  rows.forEach((row) => {
    const option = document.createElement("option");
    option.value = row.id;
    option.textContent = optionLabel(row, fallback);
    select.append(option);
  });
}

function renderSelects() {
  document.querySelectorAll('select[name="store_id"]').forEach((select) => {
    populateSelect(select, state.stores, "Store");
  });

  document.querySelectorAll('select[name="item_id"]').forEach((select) => {
    populateSelect(select, state.items, "Item");
  });

  document.querySelectorAll('select[name="tag_id"]').forEach((select) => {
    populateSelect(select, state.tags, "Tag");
  });
}

function updateFormAvailability() {
  const hasStores = state.stores.length > 0;
  const hasItems = state.items.length > 0;
  const hasTags = state.tags.length > 0;

  els.itemSubmit.disabled = !hasStores;
  els.tagSubmit.disabled = !hasStores;
  els.linkTagSubmit.disabled = !(hasItems && hasTags);
  els.reviewSubmit.disabled = !hasItems;
}

function starDisplay(rating) {
  const filled = "\u2605".repeat(rating);
  const empty = "\u2606".repeat(5 - rating);
  return `<span class="stars" title="${rating} / 5">${filled}${empty}</span>`;
}

function averageRating(itemId) {
  const itemReviews = state.reviews.filter((review) => review.item_id === itemId || review.itemId === itemId);
  if (!itemReviews.length) return null;
  const sum = itemReviews.reduce((total, review) => total + Number(review.rating), 0);
  return sum / itemReviews.length;
}

function renderDashboard() {
  els.storeCount.textContent = state.stores.length;
  els.itemCount.textContent = state.items.length;
  els.tagCount.textContent = state.tags.length;

  const recent = state.items.slice(-5).reverse();
  if (!recent.length) {
    els.recentItems.className = "compact-list empty-state";
    els.recentItems.textContent = "No items loaded.";
    return;
  }

  els.recentItems.className = "compact-list";
  els.recentItems.innerHTML = recent
    .map(
      (item) => `
        <div class="compact-row">
          <div class="compact-row-main">
            ${item.image_url ? `<img class="thumb" src="${item.image_url}" alt="${item.name}" />` : ""}
            <strong>${item.name}</strong>
          </div>
          <span>$${Number(item.price).toFixed(2)}</span>
        </div>
      `
    )
    .join("");
}

function renderStores() {
  renderTable(
    els.storesTable,
    [
      { label: "ID", value: (store) => store.id },
      { label: "Name", value: (store) => store.name },
      { label: "Items", value: (store) => store.items?.length || 0 },
      { label: "Tags", value: (store) => store.tags?.length || 0 },
      { label: "", value: (store) => `<button data-delete-store="${store.id}">Delete</button>` },
    ],
    state.stores
  );
}

function renderItems() {
  renderTable(
    els.itemsTable,
    [
      {
        label: "Image",
        value: (item) =>
          item.image_url
            ? `<img class="thumb" src="${item.image_url}" alt="${item.name}" />`
            : `<span class="muted">None</span>`,
      },
      { label: "ID", value: (item) => item.id },
      { label: "Name", value: (item) => item.name },
      { label: "Price", value: (item) => `$${Number(item.price).toFixed(2)}` },
      {
        label: "Rating",
        value: (item) => {
          const avg = averageRating(item.id);
          return avg ? starDisplay(Math.round(avg)) : `<span class="muted">No reviews</span>`;
        },
      },
      { label: "Store", value: (item) => item.store?.name || item.store_id || "Unknown" },
      { label: "Tags", value: (item) => item.tags?.map((tag) => tag.name).join(", ") || "None" },
      { label: "", value: (item) => `<button data-delete-item="${item.id}">Delete</button>` },
    ],
    state.items
  );
}

function renderTags() {
  renderTable(
    els.tagsTable,
    [
      { label: "ID", value: (tag) => tag.id },
      { label: "Name", value: (tag) => tag.name },
      { label: "Store", value: (tag) => tag.store?.name || tag.store_id || "Unknown" },
      { label: "Items", value: (tag) => tag.items?.length || 0 },
      { label: "", value: (tag) => `<button data-delete-tag="${tag.id}">Delete</button>` },
    ],
    state.tags
  );
}

function itemNameForReview(review) {
  const itemId = review.item_id ?? review.itemId;
  const item = state.items.find((candidate) => candidate.id === itemId);
  return item ? item.name : `Item #${itemId}`;
}

function renderReviews() {
  renderTable(
    els.reviewsTable,
    [
      { label: "Item", value: (review) => itemNameForReview(review) },
      { label: "Rating", value: (review) => starDisplay(Number(review.rating)) },
      { label: "Comment", value: (review) => review.comment || "" },
      {
        label: "",
        value: (review) => `<button data-delete-review="${review.id}">Delete</button>`,
      },
    ],
    state.reviews
  );
}

function renderAll() {
  updateAuthUi();
  renderSelects();
  updateFormAvailability();
  renderDashboard();
  renderStores();
  renderItems();
  renderTags();
  renderReviews();
}

async function loadData() {
  try {
    const [stores, items] = await Promise.all([request("/store"), request("/item")]);
    state.stores = stores || [];
    state.items = items || [];

    const tagGroups = await Promise.all(
      state.stores.map((store) => request(`/store/${store.id}/tag`).catch(() => []))
    );
    state.tags = tagGroups.flat();

    const reviewGroups = await Promise.all(
      state.items.map((item) => request(`/item/${item.id}/review`).catch(() => []))
    );
    state.reviews = reviewGroups.flat().map((review, index) => ({
      ...review,
      item_id: review.item_id ?? state.items[reviewGroups.findIndex((group) => group.includes(review))]?.id,
    }));

    els.connectionState.textContent = "Connected";
    setAlert("Data loaded.");
  } catch (error) {
    els.connectionState.textContent = "Connection failed";
    setAlert(error.message, "error");
  }

  renderAll();
}

async function submitJson(form, path, transform = (data) => data) {
  const submitButton = form.querySelector("button[type='submit']");
  const payload = transform(formData(form));
  if (submitButton) submitButton.disabled = true;
  try {
    await request(path, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    form.reset();
    await loadData();
  } finally {
    if (submitButton) submitButton.disabled = false;
  }
}

async function deleteRecord(path) {
  await request(path, { method: "DELETE" });
  await loadData();
}

els.storesTable.addEventListener("click", async (event) => {
  const id = event.target.dataset.deleteStore;
  if (!id) return;
  try {
    await deleteRecord(`/store/${id}`);
    setAlert("Store deleted.");
  } catch (error) {
    setAlert(error.message, "error");
  }
});

els.itemsTable.addEventListener("click", async (event) => {
  const id = event.target.dataset.deleteItem;
  if (!id) return;
  try {
    await deleteRecord(`/item/${id}`);
    setAlert("Item deleted.");
  } catch (error) {
    setAlert(error.message, "error");
  }
});

els.tagsTable.addEventListener("click", async (event) => {
  const id = event.target.dataset.deleteTag;
  if (!id) return;
  try {
    await deleteRecord(`/tag/${id}`);
    setAlert("Tag deleted.");
  } catch (error) {
    setAlert(error.message, "error");
  }
});

els.reviewsTable.addEventListener("click", async (event) => {
  const id = event.target.dataset.deleteReview;
  if (!id) return;
  try {
    await deleteRecord(`/review/${id}`);
    setAlert("Review deleted.");
  } catch (error) {
    setAlert(error.message, "error");
  }
});

document.querySelectorAll("[data-view-link]").forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    const viewName = link.dataset.viewLink;
    history.replaceState(null, "", `#${viewName}`);
    setView(viewName);
  });
});

els.menuToggle.addEventListener("click", () => {
  setMenuOpen(!document.body.classList.contains("nav-open"));
});

els.sidebarScrim.addEventListener("click", () => {
  setMenuOpen(false);
});

window.addEventListener("hashchange", () => {
  setView(location.hash.replace("#", "") || "dashboard");
});

window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    setMenuOpen(false);
  }
});

window.addEventListener("resize", () => {
  if (window.innerWidth > 980) {
    setMenuOpen(false);
  }
});

document.querySelectorAll("[data-auth-tab]").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll("[data-auth-tab]").forEach((tab) => {
      tab.classList.toggle("active", tab === button);
    });
    document.querySelectorAll(".auth-form").forEach((form) => {
      form.classList.toggle("active", form.id === `${button.dataset.authTab}Form`);
    });
  });
});

els.saveApiBase.addEventListener("click", () => {
  state.apiBase = els.apiBase.value.trim() || "http://localhost:5000";
  localStorage.setItem("niche.apiBase", state.apiBase);
  setAlert("API base URL saved.");
});

els.refreshData.addEventListener("click", loadData);
els.checkApiButton.addEventListener("click", async () => {
  try {
    await request("/store");
    els.apiCheckResult.textContent = "API is reachable.";
  } catch (error) {
    els.apiCheckResult.textContent = error.message;
  }
});

els.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const tokens = await request("/login", {
      method: "POST",
      body: JSON.stringify(formData(els.loginForm)),
    });
    state.accessToken = tokens.access_token;
    state.refreshToken = tokens.refresh_token;
    localStorage.setItem("niche.accessToken", state.accessToken);
    localStorage.setItem("niche.refreshToken", state.refreshToken);
    els.loginForm.reset();
    setAlert("Logged in.");
    await loadData();
  } catch (error) {
    setAlert(error.message, "error");
  }
});

els.registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await request("/register", {
      method: "POST",
      body: JSON.stringify(formData(els.registerForm)),
    });
    els.registerForm.reset();
    setAlert("Account created. You can log in now.");
  } catch (error) {
    setAlert(error.message, "error");
  }
});

els.logoutButton.addEventListener("click", async () => {
  try {
    if (state.accessToken) {
      await request("/logout", { method: "POST" });
    }
  } catch {
    // Clear local session even if the backend logout token is already invalid.
  }

  state.accessToken = "";
  state.refreshToken = "";
  localStorage.removeItem("niche.accessToken");
  localStorage.removeItem("niche.refreshToken");
  setAlert("Logged out.");
  renderAll();
});

els.storeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await submitJson(els.storeForm, "/store");
  } catch (error) {
    setAlert(error.message, "error");
  }
});

els.itemForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    await submitJson(els.itemForm, "/item", (data) => ({
      name: data.name,
      price: Number(data.price),
      image_url: data.image_url || undefined,
      store_id: Number(data.store_id),
    }));
  } catch (error) {
    setAlert(error.message, "error");
  }
});

els.tagForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = formData(els.tagForm);
  try {
    await submitJson(els.tagForm, `/store/${Number(data.store_id)}/tag`, () => ({
      name: data.name,
    }));
  } catch (error) {
    setAlert(error.message, "error");
  }
});

els.linkTagForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = formData(els.linkTagForm);
  try {
    await request(`/item/${Number(data.item_id)}/tag/${Number(data.tag_id)}`, {
      method: "POST",
      body: JSON.stringify({}),
    });
    els.linkTagForm.reset();
    await loadData();
  } catch (error) {
    setAlert(error.message, "error");
  }
});

els.reviewForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const data = formData(els.reviewForm);
  const itemId = Number(data.item_id);
  try {
    await submitJson(els.reviewForm, `/item/${itemId}/review`, () => ({
      rating: Number(data.rating),
      comment: data.comment || undefined,
    }));
  } catch (error) {
    setAlert(error.message, "error");
  }
});

setView(location.hash.replace("#", "") || "dashboard");
renderAll();
loadData();