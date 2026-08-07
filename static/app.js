/* Niche console.
 *
 * The whole UI is gated on one thing: the signed-in account's role.
 *   customer   -> browse, order, review
 *   shopkeeper -> stores, inventory, tags, incoming orders, read-only feedback
 *   admin      -> the shopkeeper console plus users and the activity log
 *
 * Nothing here is a security boundary; the API enforces every rule
 * independently. Hiding controls a role cannot use just avoids showing people
 * buttons that would only ever return 403.
 */

const state = {
  apiBase: localStorage.getItem("niche.apiBase") || window.location.origin,
  accessToken: localStorage.getItem("niche.accessToken") || "",
  refreshToken: localStorage.getItem("niche.refreshToken") || "",
  role: localStorage.getItem("niche.role") || "",
  username: localStorage.getItem("niche.username") || "",
  userId: Number(localStorage.getItem("niche.userId")) || null,
  isAdmin: localStorage.getItem("niche.isAdmin") === "true",
  authRole: "customer", // which tab the auth screen is showing
  stores: [],
  items: [],
  tags: [],
  myOrders: [],
  myReviews: [],
  storeOrders: [],
  feedback: null,
  users: [],
  activity: [],
  search: "",
};

const $ = (selector) => document.querySelector(selector);

const els = {
  authGate: $("#authGate"),
  appShell: $("#appShell"),
  authAlert: $("#authAlert"),
  alertRegion: $("#alertRegion"),
  loginForm: $("#loginForm"),
  registerForm: $("#registerForm"),
  apiBase: $("#apiBase"),
  saveApiBase: $("#saveApiBase"),
  connectionState: $("#connectionState"),
  accountName: $("#accountName"),
  accountRole: $("#accountRole"),
  accountAvatar: $("#accountAvatar"),
  roleCaption: $("#roleCaption"),
  logoutButton: $("#logoutButton"),
  refreshData: $("#refreshData"),
  viewTitle: $("#viewTitle"),
  viewEyebrow: $("#viewEyebrow"),
  menuToggle: $("#menuToggle"),
  sidebarScrim: $("#sidebarScrim"),
  // customer
  catalogue: $("#catalogue"),
  browseSearch: $("#browseSearch"),
  browseItemCount: $("#browseItemCount"),
  browseStoreCount: $("#browseStoreCount"),
  browseOrderCount: $("#browseOrderCount"),
  browseReviewCount: $("#browseReviewCount"),
  myOrdersTable: $("#myOrdersTable"),
  myReviewsTable: $("#myReviewsTable"),
  // shopkeeper
  storeCount: $("#storeCount"),
  itemCount: $("#itemCount"),
  pendingCount: $("#pendingCount"),
  overallRating: $("#overallRating"),
  overallStars: $("#overallStars"),
  recentItems: $("#recentItems"),
  recentFeedback: $("#recentFeedback"),
  storesTable: $("#storesTable"),
  itemsTable: $("#itemsTable"),
  tagsTable: $("#tagsTable"),
  storeForm: $("#storeForm"),
  itemForm: $("#itemForm"),
  tagForm: $("#tagForm"),
  linkTagForm: $("#linkTagForm"),
  salesTable: $("#salesTable"),
  salesStoreSelect: $("#salesStoreSelect"),
  feedbackStoreSelect: $("#feedbackStoreSelect"),
  feedbackAverage: $("#feedbackAverage"),
  feedbackStars: $("#feedbackStars"),
  feedbackCount: $("#feedbackCount"),
  ratingBreakdown: $("#ratingBreakdown"),
  perItemRatings: $("#perItemRatings"),
  feedbackList: $("#feedbackList"),
  // admin
  usersTable: $("#usersTable"),
  activityTable: $("#activityTable"),
};

els.apiBase.value = state.apiBase;

/* ------------------------------------------------------------------ */
/* DOM helpers — everything is built as nodes, never as HTML strings,  */
/* because item names, comments and usernames are user-supplied.       */
/* ------------------------------------------------------------------ */

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function safeImageUrl(value) {
  if (!value) return null;
  try {
    const url = new URL(value, window.location.href);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

function thumbnail(item, className = "thumb") {
  const src = safeImageUrl(item.image_url);
  if (!src) return null;
  const img = el("img", className);
  img.src = src;
  img.alt = item.name || "";
  img.loading = "lazy";
  return img;
}

// Renders a fractional average (4.33) exactly, by overlaying a gold row of
// stars clipped to the right percentage over a grey one. Partial-star glyphs
// like U+2BE8 were tried first but render as a blank box in most fonts.
function starNode(rating) {
  const value = Math.max(0, Math.min(5, Number(rating) || 0));
  const wrap = el("span", "stars");
  wrap.title = `${value.toFixed(2)} out of 5`;
  wrap.setAttribute("role", "img");
  wrap.setAttribute("aria-label", `${value.toFixed(2)} out of 5 stars`);

  wrap.append(el("span", "stars-base", "★★★★★"));
  const fill = el("span", "stars-fill", "★★★★★");
  fill.style.width = `${(value / 5) * 100}%`;
  wrap.append(fill);
  return wrap;
}

function money(value) {
  return `$${Number(value || 0).toFixed(2)}`;
}

function button(label, className, onClick) {
  const node = el("button", className, label);
  node.type = "button";
  node.addEventListener("click", onClick);
  return node;
}

function statusPill(status) {
  return el("span", `status-pill status-${status}`, status);
}

function renderTable(target, columns, rows, emptyMessage = "Nothing here yet.") {
  if (!rows.length) {
    target.className = "data-table empty-state";
    target.textContent = emptyMessage;
    return;
  }
  target.className = "data-table";

  const table = el("table");
  const headRow = el("tr");
  columns.forEach((column) => headRow.append(el("th", null, column.label)));
  const thead = el("thead");
  thead.append(headRow);

  const tbody = el("tbody");
  rows.forEach((row) => {
    const tr = el("tr");
    columns.forEach((column) => {
      const td = el("td");
      const value = column.value(row);
      if (value instanceof Node) td.append(value);
      else td.textContent = value == null ? "" : String(value);
      tr.append(td);
    });
    tbody.append(tr);
  });

  table.append(thead, tbody);
  target.replaceChildren(table);
}

function setAlert(message, type = "info", region = els.alertRegion) {
  region.replaceChildren();
  if (!message) return;
  region.append(el("div", `alert ${type}`, message));
}

/* ------------------------------------------------------------------ */
/* Networking                                                          */
/* ------------------------------------------------------------------ */

function apiUrl(path) {
  return `${state.apiBase.replace(/\/$/, "")}${path}`;
}

function storeSession({ access_token, refresh_token, role, username, is_admin, id }) {
  if (access_token) {
    state.accessToken = access_token;
    localStorage.setItem("niche.accessToken", access_token);
  }
  if (refresh_token) {
    state.refreshToken = refresh_token;
    localStorage.setItem("niche.refreshToken", refresh_token);
  }
  if (role) {
    state.role = role;
    localStorage.setItem("niche.role", role);
  }
  if (username) {
    state.username = username;
    localStorage.setItem("niche.username", username);
  }
  if (is_admin !== undefined) {
    state.isAdmin = Boolean(is_admin);
    localStorage.setItem("niche.isAdmin", String(state.isAdmin));
  }
  if (id !== undefined && id !== null) {
    state.userId = Number(id);
    localStorage.setItem("niche.userId", String(state.userId));
  }
}

function clearSession() {
  state.accessToken = "";
  state.refreshToken = "";
  state.role = "";
  state.username = "";
  state.userId = null;
  state.isAdmin = false;
  ["accessToken", "refreshToken", "role", "username", "userId", "isAdmin"].forEach((key) =>
    localStorage.removeItem(`niche.${key}`)
  );
}

let refreshInFlight = null;

async function refreshAccessToken() {
  if (!state.refreshToken) return false;
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const response = await fetch(apiUrl("/refresh"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${state.refreshToken}`,
          },
        });
        if (!response.ok) return false;
        storeSession(await response.json());
        return true;
      } catch {
        return false;
      } finally {
        setTimeout(() => {
          refreshInFlight = null;
        }, 0);
      }
    })();
  }
  return refreshInFlight;
}

async function rawRequest(path, options, token) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  return fetch(apiUrl(path), { ...options, headers });
}

async function request(path, options = {}, allowRetry = true) {
  let response = await rawRequest(path, options, state.accessToken);

  // An expired access token is recoverable: refresh once, then replay.
  if (response.status === 401 && allowRetry && state.refreshToken && path !== "/refresh") {
    if (await refreshAccessToken()) {
      response = await rawRequest(path, options, state.accessToken);
    } else {
      clearSession();
      showAuthGate();
    }
  }

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
    // Marshmallow validation errors arrive as {errors: {json: {field: [...]}}}.
    const fieldErrors = body?.errors?.json;
    if (fieldErrors) {
      const first = Object.entries(fieldErrors)[0];
      throw new Error(first ? `${first[0]}: ${[].concat(first[1]).join(", ")}` : "Invalid input.");
    }
    throw new Error(body?.message || body?.description || `Request failed (${response.status})`);
  }
  return body;
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}

/* ------------------------------------------------------------------ */
/* Auth screen                                                         */
/* ------------------------------------------------------------------ */

const ROLE_COPY = {
  customer: {
    caption: "Storefront",
    hint: "Customer accounts browse, order and leave reviews. They cannot open a store.",
  },
  shopkeeper: {
    caption: "Seller console",
    hint: "Shopkeeper accounts open stores and sell. They can read customer reviews but cannot write them.",
  },
};

function setAuthRole(role) {
  state.authRole = role;
  document.querySelectorAll("[data-role]").forEach((node) => {
    const active = node.dataset.role === role;
    node.classList.toggle("active", active);
    node.setAttribute("aria-selected", String(active));
  });
  document.querySelectorAll("[data-role-label]").forEach((node) => {
    node.textContent = role;
  });
  document.querySelectorAll("[data-role-hint]").forEach((node) => {
    node.textContent = ROLE_COPY[role].hint;
  });
  document.body.dataset.authRole = role;
}

function showAuthGate() {
  els.authGate.hidden = false;
  els.appShell.hidden = true;
  document.body.classList.remove("signed-in");
}

function showConsole() {
  els.authGate.hidden = true;
  els.appShell.hidden = false;
  document.body.classList.add("signed-in");
}

document.querySelectorAll("[data-role]").forEach((node) => {
  node.addEventListener("click", () => setAuthRole(node.dataset.role));
});

document.querySelectorAll("[data-auth-mode]").forEach((node) => {
  node.addEventListener("click", () => {
    document.querySelectorAll("[data-auth-mode]").forEach((tab) => {
      tab.classList.toggle("active", tab === node);
    });
    document.querySelectorAll(".auth-form").forEach((form) => {
      form.classList.toggle("active", form.id === `${node.dataset.authMode}Form`);
    });
    setAlert("", "info", els.authAlert);
  });
});

els.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = els.loginForm.querySelector("button[type=submit]");
  submit.disabled = true;
  try {
    const body = { ...formData(els.loginForm), role: state.authRole };
    storeSession(await request("/login", { method: "POST", body: JSON.stringify(body) }));
    els.loginForm.reset();
    setAlert("", "info", els.authAlert);
    await enterConsole();
  } catch (error) {
    setAlert(error.message, "error", els.authAlert);
  } finally {
    submit.disabled = false;
  }
});

els.registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = els.registerForm.querySelector("button[type=submit]");
  submit.disabled = true;
  try {
    const body = { ...formData(els.registerForm), role: state.authRole };
    await request("/register", { method: "POST", body: JSON.stringify(body) });
    // Registration does not sign you in, so log straight in with the same
    // credentials rather than making the user type them twice.
    storeSession(
      await request("/login", {
        method: "POST",
        body: JSON.stringify({ username: body.username, password: body.password, role: state.authRole }),
      })
    );
    els.registerForm.reset();
    await enterConsole();
  } catch (error) {
    setAlert(error.message, "error", els.authAlert);
  } finally {
    submit.disabled = false;
  }
});

els.saveApiBase.addEventListener("click", () => {
  state.apiBase = els.apiBase.value.trim() || window.location.origin;
  localStorage.setItem("niche.apiBase", state.apiBase);
  els.connectionState.textContent = "Saved.";
});

els.logoutButton.addEventListener("click", async () => {
  try {
    if (state.accessToken) await request("/logout", { method: "POST" });
  } catch {
    // Clear the local session even if the token was already invalid.
  }
  clearSession();
  showAuthGate();
});

/* ------------------------------------------------------------------ */
/* Navigation                                                          */
/* ------------------------------------------------------------------ */

function visibleNavLinks() {
  return [...document.querySelectorAll("[data-view-link]")].filter(
    (link) => !link.hidden
  );
}

function applyRoleVisibility() {
  const shopkeeper = state.role === "shopkeeper" || state.isAdmin;
  const customer = state.role === "customer";

  document.querySelectorAll("[data-nav-role]").forEach((link) => {
    const needed = link.dataset.navRole;
    const allowed =
      (needed === "customer" && customer) ||
      (needed === "shopkeeper" && shopkeeper) ||
      (needed === "admin" && state.isAdmin);
    link.hidden = !allowed;
  });

  els.accountName.textContent = state.username || "—";
  els.accountAvatar.textContent = (state.username || "?").charAt(0).toUpperCase();
  els.accountRole.textContent = state.isAdmin ? "admin" : state.role || "—";
  els.accountRole.className = `role-badge role-${state.isAdmin ? "admin" : state.role}`;
  els.roleCaption.textContent = ROLE_COPY[state.role]?.caption || "Console";
}

function setView(viewName) {
  const links = visibleNavLinks();
  const allowed = links.map((link) => link.dataset.viewLink);
  const target = allowed.includes(viewName) ? viewName : allowed[0];
  if (!target) return;

  document.querySelectorAll("[data-view]").forEach((view) => {
    view.classList.toggle("active", view.dataset.view === target);
  });
  links.forEach((link) => {
    link.classList.toggle("active", link.dataset.viewLink === target);
  });

  const active = links.find((link) => link.dataset.viewLink === target);
  els.viewTitle.textContent = active ? active.textContent : target;
  els.viewEyebrow.textContent = ROLE_COPY[state.role]?.caption || "Console";
  setMenuOpen(false);

  // Views whose data is fetched on demand rather than up front.
  if (target === "sales") loadStoreOrders();
  if (target === "feedback") loadFeedback();
  if (target === "admin") loadUsers();
  if (target === "activity") loadActivity();
}

function setMenuOpen(isOpen) {
  document.body.classList.toggle("nav-open", isOpen);
  els.menuToggle.setAttribute("aria-expanded", String(isOpen));
}

document.querySelectorAll("[data-view-link]").forEach((link) => {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    history.replaceState(null, "", `#${link.dataset.viewLink}`);
    setView(link.dataset.viewLink);
  });
});

els.menuToggle.addEventListener("click", () =>
  setMenuOpen(!document.body.classList.contains("nav-open"))
);
els.sidebarScrim.addEventListener("click", () => setMenuOpen(false));
window.addEventListener("hashchange", () => setView(location.hash.replace("#", "")));
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setMenuOpen(false);
});
window.addEventListener("resize", () => {
  if (window.innerWidth > 980) setMenuOpen(false);
});

/* ------------------------------------------------------------------ */
/* Customer views                                                      */
/* ------------------------------------------------------------------ */

function renderCatalogue() {
  const term = state.search.trim().toLowerCase();
  const items = state.items.filter(
    (item) => !term || item.name.toLowerCase().includes(term)
  );

  els.browseItemCount.textContent = state.items.length;
  els.browseStoreCount.textContent = state.stores.length;
  els.browseOrderCount.textContent = state.myOrders.length;
  els.browseReviewCount.textContent = state.myReviews.length;

  if (!items.length) {
    els.catalogue.className = "catalogue empty-state";
    els.catalogue.textContent = term ? "No items match that search." : "Nothing for sale yet.";
    return;
  }

  els.catalogue.className = "catalogue";
  els.catalogue.replaceChildren(
    ...items.map((item) => {
      const card = el("article", "product-card");

      const media = el("div", "product-media");
      const img = thumbnail(item, "product-image");
      media.append(img || el("div", "product-placeholder", "No image"));
      card.append(media);

      const body = el("div", "product-body");
      body.append(el("h4", null, item.name));
      body.append(el("p", "product-store", item.store?.name || "Unknown store"));

      const ratingRow = el("div", "product-rating");
      ratingRow.append(starNode(item.average_rating));
      ratingRow.append(
        el(
          "span",
          "muted",
          item.review_count
            ? `${Number(item.average_rating).toFixed(2)} (${item.review_count})`
            : "no reviews"
        )
      );
      body.append(ratingRow);

      if (item.tags?.length) {
        const tagRow = el("div", "tag-row");
        item.tags.forEach((tag) => tagRow.append(el("span", "tag-chip", tag.name)));
        body.append(tagRow);
      }

      const footer = el("div", "product-footer");
      footer.append(el("strong", "price", money(item.price)));

      const alreadyReviewed = state.myReviews.some((review) => review.item_id === item.id);
      const actions = el("div", "product-actions");
      actions.append(button("Buy", "small", () => placeOrder(item)));
      actions.append(
        button(alreadyReviewed ? "Reviewed" : "Review", "small ghost", () => openReview(item), )
      );
      actions.lastChild.disabled = alreadyReviewed;
      footer.append(actions);

      body.append(footer);
      card.append(body);
      return card;
    })
  );
}

async function placeOrder(item) {
  const raw = window.prompt(`How many "${item.name}"?`, "1");
  if (raw === null) return;
  const quantity = Number(raw);
  if (!Number.isInteger(quantity) || quantity < 1) {
    setAlert("Quantity must be a whole number of at least 1.", "error");
    return;
  }
  try {
    await request(`/item/${item.id}/order`, {
      method: "POST",
      body: JSON.stringify({ quantity }),
    });
    setAlert(`Ordered ${quantity} × ${item.name}.`, "success");
    await loadCustomerData();
  } catch (error) {
    setAlert(error.message, "error");
  }
}

async function openReview(item) {
  const raw = window.prompt(`Rate "${item.name}" from 1 to 5:`, "5");
  if (raw === null) return;
  const rating = Number(raw);
  if (!Number.isInteger(rating) || rating < 1 || rating > 5) {
    setAlert("Rating must be a whole number from 1 to 5.", "error");
    return;
  }
  const comment = window.prompt("Add a comment (optional):", "") || undefined;
  try {
    await request(`/item/${item.id}/review`, {
      method: "POST",
      body: JSON.stringify({ rating, comment }),
    });
    setAlert("Review posted.", "success");
    await loadCustomerData();
  } catch (error) {
    setAlert(error.message, "error");
  }
}

function renderMyOrders() {
  renderTable(
    els.myOrdersTable,
    [
      { label: "Item", value: (order) => order.item?.name || `Item #${order.item_id}` },
      { label: "Qty", value: (order) => order.quantity },
      { label: "Status", value: (order) => statusPill(order.status) },
      { label: "Placed", value: (order) => new Date(order.created_at).toLocaleString() },
      {
        label: "",
        value: (order) =>
          order.status === "pending"
            ? button("Cancel", "small danger", () => cancelOrder(order))
            : el("span", "muted", "—"),
      },
    ],
    state.myOrders,
    "You have not ordered anything yet."
  );
}

async function cancelOrder(order) {
  try {
    await request(`/order/${order.id}/cancel`, { method: "POST" });
    setAlert("Order cancelled.", "success");
    await loadCustomerData();
  } catch (error) {
    setAlert(error.message, "error");
  }
}

function renderMyReviews() {
  renderTable(
    els.myReviewsTable,
    [
      {
        label: "Item",
        value: (review) =>
          state.items.find((item) => item.id === review.item_id)?.name ||
          `Item #${review.item_id}`,
      },
      { label: "Rating", value: (review) => starNode(review.rating) },
      { label: "Comment", value: (review) => review.comment || "—" },
      {
        label: "",
        value: (review) => button("Delete", "small danger", () => deleteReview(review)),
      },
    ],
    state.myReviews,
    "You have not reviewed anything yet."
  );
}

async function deleteReview(review) {
  try {
    await request(`/review/${review.id}`, { method: "DELETE" });
    setAlert("Review deleted.", "success");
    await loadCustomerData();
  } catch (error) {
    setAlert(error.message, "error");
  }
}

/* ------------------------------------------------------------------ */
/* Shopkeeper views                                                    */
/* ------------------------------------------------------------------ */

// GET /store returns every store on the platform, so the seller console has
// to narrow it down. Admins moderate, so they keep the full list.
function myStores() {
  if (state.isAdmin) return state.stores;
  return state.stores.filter((store) => store.owner_id === state.userId);
}

function myStoreIds() {
  return new Set(myStores().map((store) => store.id));
}

function myItems() {
  if (state.isAdmin) return state.items;
  const ids = myStoreIds();
  return state.items.filter((item) => ids.has(item.store?.id ?? item.store_id));
}

function myTags() {
  if (state.isAdmin) return state.tags;
  const ids = myStoreIds();
  return state.tags.filter((tag) => ids.has(tag.store?.id ?? tag.store_id));
}

function renderDashboard() {
  const stores = myStores();
  els.storeCount.textContent = stores.length;
  els.itemCount.textContent = myItems().length;
  els.pendingCount.textContent = state.storeOrders.filter(
    (order) => order.status === "pending"
  ).length;

  // Weighted mean across stores: a store with 50 reviews should count for more
  // than one with a single five-star rating.
  const totalReviews = stores.reduce((sum, store) => sum + (store.review_count || 0), 0);
  const weighted = stores.reduce(
    (sum, store) => sum + (store.average_rating || 0) * (store.review_count || 0),
    0
  );
  const average = totalReviews ? weighted / totalReviews : 0;
  els.overallRating.textContent = average.toFixed(2);
  els.overallStars.replaceChildren(starNode(average));

  const recent = myItems().slice(-5).reverse();
  if (!recent.length) {
    els.recentItems.className = "compact-list empty-state";
    els.recentItems.textContent = "No items yet.";
  } else {
    els.recentItems.className = "compact-list";
    els.recentItems.replaceChildren(
      ...recent.map((item) => {
        const row = el("div", "compact-row");
        const main = el("div", "compact-row-main");
        const img = thumbnail(item);
        if (img) main.append(img);
        main.append(el("strong", null, item.name));
        row.append(main, el("span", null, money(item.price)));
        return row;
      })
    );
  }

  const reviews = state.feedback?.reviews?.slice(0, 5) || [];
  if (!reviews.length) {
    els.recentFeedback.className = "compact-list empty-state";
    els.recentFeedback.textContent = "No reviews yet.";
  } else {
    els.recentFeedback.className = "compact-list";
    els.recentFeedback.replaceChildren(
      ...reviews.map((review) => {
        const row = el("div", "compact-row column");
        const head = el("div", "compact-row-main");
        head.append(starNode(review.rating));
        head.append(el("span", "muted", review.item_name || ""));
        row.append(head);
        if (review.comment) row.append(el("p", "review-comment", review.comment));
        return row;
      })
    );
  }
}

function renderStores() {
  renderTable(
    els.storesTable,
    [
      { label: "Store", value: (store) => store.name },
      { label: "Items", value: (store) => store.items?.length || 0 },
      {
        label: "Rating",
        value: (store) => {
          if (!store.review_count) return el("span", "muted", "no reviews");
          const wrap = el("div", "inline-rating");
          wrap.append(starNode(store.average_rating));
          wrap.append(
            el("span", "muted", `${Number(store.average_rating).toFixed(2)} (${store.review_count})`)
          );
          return wrap;
        },
      },
      {
        label: "",
        value: (store) => button("Delete", "small danger", () => deleteStore(store)),
      },
    ],
    myStores(),
    "You have not opened a store yet."
  );
}

async function deleteStore(store) {
  if (!window.confirm(`Delete "${store.name}" and everything in it?`)) return;
  try {
    await request(`/store/${store.id}`, { method: "DELETE" });
    setAlert("Store deleted.", "success");
    await loadShopkeeperData();
  } catch (error) {
    setAlert(error.message, "error");
  }
}

function renderItems() {
  renderTable(
    els.itemsTable,
    [
      { label: "", value: (item) => thumbnail(item) || el("span", "muted", "—") },
      { label: "Item", value: (item) => item.name },
      { label: "Price", value: (item) => money(item.price) },
      {
        label: "Rating",
        value: (item) =>
          item.review_count
            ? el("span", null, `${Number(item.average_rating).toFixed(2)} ★ (${item.review_count})`)
            : el("span", "muted", "no reviews"),
      },
      { label: "Store", value: (item) => item.store?.name || "—" },
      {
        label: "Visible",
        value: (item) =>
          button(item.is_hidden ? "Hidden" : "Visible", "small ghost", () => toggleHidden(item)),
      },
      {
        label: "",
        value: (item) => {
          const wrap = el("div", "row-actions");
          wrap.append(button("Edit", "small ghost", () => editItem(item)));
          wrap.append(button("Delete", "small danger", () => deleteItem(item)));
          return wrap;
        },
      },
    ],
    myItems(),
    "No items yet."
  );
}

async function toggleHidden(item) {
  try {
    await request(`/item/${item.id}/${item.is_hidden ? "unhide" : "hide"}`, { method: "POST" });
    await loadShopkeeperData();
  } catch (error) {
    setAlert(error.message, "error");
  }
}

async function editItem(item) {
  const name = window.prompt("Item name:", item.name);
  if (name === null) return;
  const price = window.prompt("Price:", item.price);
  if (price === null) return;
  const imageUrl = window.prompt("Image URL (blank for none):", item.image_url || "");
  if (imageUrl === null) return;

  const payload = { name, price: Number(price) };
  if (imageUrl.trim()) payload.image_url = imageUrl.trim();

  try {
    await request(`/item/${item.id}`, { method: "PUT", body: JSON.stringify(payload) });
    setAlert("Item updated.", "success");
    await loadShopkeeperData();
  } catch (error) {
    setAlert(error.message, "error");
  }
}

async function deleteItem(item) {
  if (!window.confirm(`Delete "${item.name}"?`)) return;
  try {
    await request(`/item/${item.id}`, { method: "DELETE" });
    setAlert("Item deleted.", "success");
    await loadShopkeeperData();
  } catch (error) {
    setAlert(error.message, "error");
  }
}

function renderTags() {
  renderTable(
    els.tagsTable,
    [
      { label: "Tag", value: (tag) => tag.name },
      { label: "Store", value: (tag) => tag.store?.name || tag.store_id },
      { label: "Items", value: (tag) => tag.items?.length || 0 },
      { label: "", value: (tag) => button("Delete", "small danger", () => deleteTag(tag)) },
    ],
    myTags(),
    "No tags yet."
  );
}

async function deleteTag(tag) {
  try {
    await request(`/tag/${tag.id}`, { method: "DELETE" });
    setAlert("Tag deleted.", "success");
    await loadShopkeeperData();
  } catch (error) {
    setAlert(error.message, "error");
  }
}

function renderSales() {
  renderTable(
    els.salesTable,
    [
      { label: "Item", value: (order) => order.item?.name || `Item #${order.item_id}` },
      { label: "Customer", value: (order) => order.username || `User #${order.user_id}` },
      { label: "Qty", value: (order) => order.quantity },
      { label: "Status", value: (order) => statusPill(order.status) },
      { label: "Placed", value: (order) => new Date(order.created_at).toLocaleString() },
      {
        label: "",
        value: (order) => {
          if (order.status !== "pending") return el("span", "muted", "—");
          const wrap = el("div", "row-actions");
          wrap.append(button("Fulfil", "small", () => updateOrder(order, "fulfill")));
          wrap.append(button("Cancel", "small danger", () => updateOrder(order, "cancel")));
          return wrap;
        },
      },
    ],
    state.storeOrders,
    "No orders for this store yet."
  );
}

async function updateOrder(order, action) {
  try {
    await request(`/order/${order.id}/${action}`, { method: "POST" });
    setAlert(`Order ${action === "fulfill" ? "fulfilled" : "cancelled"}.`, "success");
    await loadStoreOrders();
  } catch (error) {
    setAlert(error.message, "error");
  }
}

function renderFeedback() {
  const data = state.feedback;
  if (!data) return;

  els.feedbackAverage.textContent = Number(data.average_rating).toFixed(2);
  els.feedbackStars.replaceChildren(starNode(data.average_rating));
  els.feedbackCount.textContent = data.review_count
    ? `${data.review_count} review${data.review_count === 1 ? "" : "s"}`
    : "no reviews";

  // Distribution bars, 5 stars down to 1.
  const max = Math.max(1, ...Object.values(data.rating_breakdown || {}));
  els.ratingBreakdown.replaceChildren(
    ...[5, 4, 3, 2, 1].map((star) => {
      const count = data.rating_breakdown?.[String(star)] || 0;
      const row = el("div", "breakdown-row");
      row.append(el("span", "breakdown-label", `${star}★`));
      const track = el("div", "breakdown-track");
      const fill = el("div", "breakdown-fill");
      fill.style.width = `${(count / max) * 100}%`;
      track.append(fill);
      row.append(track, el("span", "breakdown-count", count));
      return row;
    })
  );

  const perItem = data.per_item || [];
  if (!perItem.length) {
    els.perItemRatings.className = "compact-list empty-state";
    els.perItemRatings.textContent = "No items.";
  } else {
    els.perItemRatings.className = "compact-list";
    els.perItemRatings.replaceChildren(
      ...perItem.map((row) => {
        const line = el("div", "compact-row");
        line.append(el("strong", null, row.item_name));
        const right = el("div", "compact-row-main");
        right.append(starNode(row.average_rating));
        right.append(
          el("span", "muted", row.review_count ? row.average_rating.toFixed(2) : "—")
        );
        line.append(right);
        return line;
      })
    );
  }

  const reviews = data.reviews || [];
  if (!reviews.length) {
    els.feedbackList.className = "review-list empty-state";
    els.feedbackList.textContent = "No reviews yet.";
    return;
  }
  els.feedbackList.className = "review-list";
  els.feedbackList.replaceChildren(
    ...reviews.map((review) => {
      const card = el("article", "review-card");
      const head = el("div", "review-head");
      head.append(starNode(review.rating));
      head.append(el("strong", null, review.item_name || ""));
      head.append(
        el("span", "muted", `${review.username || "customer"} · ${new Date(review.created_at).toLocaleDateString()}`)
      );
      card.append(head);
      card.append(
        review.comment
          ? el("p", "review-comment", review.comment)
          : el("p", "review-comment muted", "No comment left.")
      );
      return card;
    })
  );
}

/* ------------------------------------------------------------------ */
/* Admin views                                                         */
/* ------------------------------------------------------------------ */

function renderUsers() {
  renderTable(
    els.usersTable,
    [
      { label: "User", value: (user) => user.username },
      { label: "Role", value: (user) => el("span", `role-badge role-${user.role}`, user.role) },
      { label: "Admin", value: (user) => (user.is_admin ? "yes" : "—") },
      {
        label: "Status",
        value: (user) => (user.is_banned ? statusPill("cancelled") : statusPill("fulfilled")),
      },
      { label: "Stores", value: (user) => user.stores?.length || 0 },
      {
        label: "",
        value: (user) => {
          if (user.is_admin) return el("span", "muted", "—");
          const wrap = el("div", "row-actions");
          wrap.append(
            button(user.is_banned ? "Unban" : "Ban", "small ghost", () =>
              banUser(user, user.is_banned ? "unban" : "ban")
            )
          );
          return wrap;
        },
      },
    ],
    state.users,
    "No users."
  );
}

async function banUser(user, action) {
  try {
    await request(`/user/${user.id}/${action}`, { method: "POST" });
    setAlert(`${user.username} ${action}ned.`, "success");
    await loadUsers();
  } catch (error) {
    setAlert(error.message, "error");
  }
}

function renderActivity() {
  renderTable(
    els.activityTable,
    [
      { label: "When", value: (row) => new Date(row.created_at).toLocaleString() },
      { label: "Who", value: (row) => row.username || "—" },
      { label: "Action", value: (row) => row.action },
      { label: "Details", value: (row) => row.details || "" },
    ],
    state.activity,
    "No activity recorded."
  );
}

/* ------------------------------------------------------------------ */
/* Data loading                                                        */
/* ------------------------------------------------------------------ */

function populateSelect(select, rows, valueKey = "id", labelKey = "name") {
  const previous = select.value;
  select.replaceChildren(
    ...rows.map((row) => {
      const option = el("option", null, row[labelKey] || `#${row[valueKey]}`);
      option.value = row[valueKey];
      return option;
    })
  );
  if (previous && rows.some((row) => String(row[valueKey]) === previous)) {
    select.value = previous;
  }
}

async function loadCustomerData() {
  const [items, stores, orders] = await Promise.all([
    request("/item"),
    request("/store"),
    request("/orders"),
  ]);
  state.items = items || [];
  state.stores = stores || [];
  state.myOrders = orders || [];

  // There is no "my reviews" endpoint, so pick them out of each item's review
  // list by matching the signed-in user's id.
  const reviewGroups = await Promise.all(
    state.items.map((item) =>
      request(`/item/${item.id}/review`)
        .then((rows) => (rows || []).filter((row) => row.user_id === state.userId))
        .catch(() => [])
    )
  );
  state.myReviews = reviewGroups.flat();

  renderCatalogue();
  renderMyOrders();
  renderMyReviews();
}

async function loadShopkeeperData() {
  const [items, stores] = await Promise.all([request("/item"), request("/store")]);
  state.items = items || [];
  state.stores = stores || [];

  // Tags are per-store, and only the caller's own stores are worth fetching.
  const owned = myStores();
  const tagGroups = await Promise.all(
    owned.map((store) => request(`/store/${store.id}/tag`).catch(() => []))
  );
  state.tags = tagGroups.flat();

  populateSelect(els.itemForm.querySelector("[name=store_id]"), owned);
  populateSelect(els.tagForm.querySelector("[name=store_id]"), owned);
  populateSelect(els.linkTagForm.querySelector("[name=item_id]"), myItems());
  populateSelect(els.linkTagForm.querySelector("[name=tag_id]"), myTags());
  populateSelect(els.salesStoreSelect, owned);
  populateSelect(els.feedbackStoreSelect, owned);

  renderStores();
  renderItems();
  renderTags();
  renderDashboard();

  // The dashboard shows a "Latest Feedback" panel, so fetch the first store's
  // reviews up front instead of leaving it empty until the reviews tab is
  // opened.
  if (owned.length) await loadFeedback();
}

async function loadStoreOrders() {
  const storeId = els.salesStoreSelect.value;
  if (!storeId) {
    state.storeOrders = [];
    renderSales();
    return;
  }
  try {
    state.storeOrders = (await request(`/store/${storeId}/order`)) || [];
  } catch (error) {
    state.storeOrders = [];
    setAlert(error.message, "error");
  }
  renderSales();
  renderDashboard();
}

async function loadFeedback() {
  const storeId = els.feedbackStoreSelect.value;
  if (!storeId) {
    state.feedback = null;
    return;
  }
  try {
    state.feedback = await request(`/store/${storeId}/review`);
    renderFeedback();
    renderDashboard();
  } catch (error) {
    setAlert(error.message, "error");
  }
}

async function loadUsers() {
  if (!state.isAdmin) return;
  try {
    state.users = (await request("/users")) || [];
    renderUsers();
  } catch (error) {
    setAlert(error.message, "error");
  }
}

async function loadActivity() {
  if (!state.isAdmin) return;
  try {
    state.activity = (await request("/activity?limit=200")) || [];
    renderActivity();
  } catch (error) {
    setAlert(error.message, "error");
  }
}

async function loadData() {
  try {
    if (state.role === "customer") await loadCustomerData();
    else await loadShopkeeperData();
    els.connectionState.textContent = "Connected";
  } catch (error) {
    setAlert(error.message, "error");
  }
}

async function enterConsole() {
  // Trust the server over anything cached in localStorage.
  try {
    const me = await request("/me");
    storeSession({
      id: me.id,
      role: me.role,
      username: me.username,
      is_admin: me.is_admin,
    });
  } catch {
    clearSession();
    showAuthGate();
    return;
  }

  showConsole();
  applyRoleVisibility();
  await loadData();
  setView(location.hash.replace("#", ""));
}

/* ------------------------------------------------------------------ */
/* Shopkeeper forms                                                    */
/* ------------------------------------------------------------------ */

async function submitForm(form, path, transform, onDone) {
  const submit = form.querySelector("button[type=submit]");
  if (submit) submit.disabled = true;
  try {
    await request(path(), { method: "POST", body: JSON.stringify(transform(formData(form))) });
    form.reset();
    setAlert("Saved.", "success");
    await onDone();
  } catch (error) {
    setAlert(error.message, "error");
  } finally {
    if (submit) submit.disabled = false;
  }
}

els.storeForm.addEventListener("submit", (event) => {
  event.preventDefault();
  submitForm(els.storeForm, () => "/store", (data) => ({ name: data.name }), loadShopkeeperData);
});

els.itemForm.addEventListener("submit", (event) => {
  event.preventDefault();
  submitForm(
    els.itemForm,
    () => "/item",
    (data) => ({
      name: data.name,
      price: Number(data.price),
      store_id: Number(data.store_id),
      ...(data.image_url ? { image_url: data.image_url } : {}),
    }),
    loadShopkeeperData
  );
});

els.tagForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const data = formData(els.tagForm);
  submitForm(
    els.tagForm,
    () => `/store/${Number(data.store_id)}/tag`,
    () => ({ name: data.name }),
    loadShopkeeperData
  );
});

els.linkTagForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const data = formData(els.linkTagForm);
  submitForm(
    els.linkTagForm,
    () => `/item/${Number(data.item_id)}/tag/${Number(data.tag_id)}`,
    () => ({}),
    loadShopkeeperData
  );
});

els.salesStoreSelect.addEventListener("change", loadStoreOrders);
els.feedbackStoreSelect.addEventListener("change", loadFeedback);

els.refreshData.addEventListener("click", async () => {
  await loadData();
  // loadData only refreshes the role's core data; the on-demand views need
  // their own reload or Refresh would appear to do nothing on them.
  const active = document.querySelector(".view.active")?.dataset.view;
  if (active === "sales") await loadStoreOrders();
  if (active === "feedback") await loadFeedback();
  if (active === "admin") await loadUsers();
  if (active === "activity") await loadActivity();
});
els.browseSearch.addEventListener("input", (event) => {
  state.search = event.target.value;
  renderCatalogue();
});

/* ------------------------------------------------------------------ */
/* Boot                                                                */
/* ------------------------------------------------------------------ */

setAuthRole("customer");
if (state.accessToken) {
  enterConsole();
} else {
  showAuthGate();
}
