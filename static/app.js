const LOW_STOCK = 5;

const sessionStore = createStore({
  apiBase: localStorage.getItem("niche.apiBase") || window.location.origin,
  accessToken: localStorage.getItem("niche.accessToken") || "",
  refreshToken: localStorage.getItem("niche.refreshToken") || "",
  role: localStorage.getItem("niche.role") || "",
  username: localStorage.getItem("niche.username") || "",
  userId: Number(localStorage.getItem("niche.userId")) || null,
  isAdmin: localStorage.getItem("niche.isAdmin") === "true",
});

sessionStore.subscribe((next) => {
  localStorage.setItem("niche.apiBase", next.apiBase);
  localStorage.setItem("niche.accessToken", next.accessToken || "");
  localStorage.setItem("niche.refreshToken", next.refreshToken || "");
  localStorage.setItem("niche.role", next.role || "");
  localStorage.setItem("niche.username", next.username || "");
  localStorage.setItem("niche.isAdmin", String(next.isAdmin));
  if (next.userId != null) localStorage.setItem("niche.userId", String(next.userId));
  else localStorage.removeItem("niche.userId");
});

const state = {
  get apiBase() {
    return sessionStore.get().apiBase;
  },
  get accessToken() {
    return sessionStore.get().accessToken;
  },
  get refreshToken() {
    return sessionStore.get().refreshToken;
  },
  get role() {
    return sessionStore.get().role;
  },
  get username() {
    return sessionStore.get().username;
  },
  get userId() {
    return sessionStore.get().userId;
  },
  get isAdmin() {
    return sessionStore.get().isAdmin;
  },
  authRole: "customer",
  stores: [],
  items: [],
  tags: [],
  myOrders: [],
  myReviews: [],
  storeOrders: [],
  feedback: null,
  profile: null,
  publicRef: null,
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
  catalogue: $("#catalogue"),
  browseSearch: $("#browseSearch"),
  browseItemCount: $("#browseItemCount"),
  browseStoreCount: $("#browseStoreCount"),
  browseOrderCount: $("#browseOrderCount"),
  browseReviewCount: $("#browseReviewCount"),
  myOrdersTable: $("#myOrdersTable"),
  myReviewsTable: $("#myReviewsTable"),
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
  usersTable: $("#usersTable"),
  activityTable: $("#activityTable"),
  ordersTotalCount: $("#ordersTotalCount"),
  ordersPendingCount: $("#ordersPendingCount"),
  ordersFulfilledCount: $("#ordersFulfilledCount"),
  ordersTotalSpent: $("#ordersTotalSpent"),
  accountDetails: $("#accountDetails"),
  deliveryForm: $("#deliveryForm"),
  modalRoot: $("#modalRoot"),
  modalTitle: $("#modalTitle"),
  modalBody: $("#modalBody"),
  modalFoot: $("#modalFoot"),
};

els.apiBase.value = state.apiBase;

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
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
  }).format(Number(value || 0));
}

function button(label, className, onClick) {
  const node = el("button", className, label);
  node.type = "button";
  node.addEventListener("click", onClick);
  return node;
}

const STATUS_LABELS = {
  pending: "Pending",
  accepted: "Accepted",
  packed: "Packed",
  out_for_delivery: "Out for delivery",
  completed: "Completed",
  cancelled: "Cancelled",
};

function statusPill(status) {
  return el("span", `status-pill status-${status}`, STATUS_LABELS[status] || status);
}

function accountStatusPill(isBanned) {
  return isBanned
    ? el("span", "status-pill status-cancelled", "Banned")
    : el("span", "status-pill status-completed", "Active");
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
  columns.forEach((column) => headRow.append(el("th", column.className, column.label)));
  const thead = el("thead");
  thead.append(headRow);

  const tbody = el("tbody");
  rows.forEach((row) => {
    const tr = el("tr");
    columns.forEach((column) => {
      const td = el("td", column.className);
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

let closeModal = () => {};

function openModal({ title, body, actions, onOpen }) {
  const root = els.modalRoot;
  els.modalTitle.textContent = title;
  els.modalBody.replaceChildren(body);
  els.modalFoot.replaceChildren(...actions);
  root.hidden = false;
  document.body.classList.add("modal-open");

  const previouslyFocused = document.activeElement;

  const onKey = (event) => {
    if (event.key === "Escape") closeModal();
  };
  document.addEventListener("keydown", onKey);

  closeModal = () => {
    root.hidden = true;
    document.body.classList.remove("modal-open");
    document.removeEventListener("keydown", onKey);
    closeModal = () => {};
    if (previouslyFocused instanceof HTMLElement) previouslyFocused.focus();
  };

  root.querySelectorAll("[data-modal-dismiss]").forEach((node) => {
    node.onclick = () => closeModal();
  });

  if (onOpen) onOpen();
  else els.modalBody.querySelector("input, textarea, select, button")?.focus();
}

function confirmAction({ title, message, confirmLabel = "Confirm", danger = false }) {
  return new Promise((resolve) => {
    const body = el("p", "modal-message", message);
    const cancel = button("Keep it", "ghost", () => {
      closeModal();
      resolve(false);
    });
    const go = button(confirmLabel, danger ? "danger-solid" : "", () => {
      closeModal();
      resolve(true);
    });
    openModal({ title, body, actions: [cancel, go], onOpen: () => go.focus() });
  });
}

function apiUrl(path) {
  return `${state.apiBase.replace(/\/$/, "")}${path}`;
}

function storeSession({ access_token, refresh_token, role, username, is_admin, id }) {
  const patch = {};
  if (access_token) patch.accessToken = access_token;
  if (refresh_token) patch.refreshToken = refresh_token;
  if (role) patch.role = role;
  if (username) patch.username = username;
  if (is_admin !== undefined) patch.isAdmin = Boolean(is_admin);
  if (id !== undefined && id !== null) patch.userId = Number(id);
  sessionStore.set(patch);
}

function clearSession() {
  sessionStore.set({
    accessToken: "",
    refreshToken: "",
    role: "",
    username: "",
    userId: null,
    isAdmin: false,
  });
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
  sessionStore.set({ apiBase: els.apiBase.value.trim() || window.location.origin });
  els.connectionState.textContent = "Saved.";
});

els.logoutButton.addEventListener("click", async () => {
  try {
    if (state.accessToken) await request("/logout", { method: "POST" });
  } catch {
  }
  clearSession();
  showAuthGate();
});

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

sessionStore.select(["role", "isAdmin", "username"], applyRoleVisibility);

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
      const priceRow = el("div", "product-price-row");
      priceRow.append(el("strong", "price", money(item.price)));
      priceRow.append(stockLabel(item));
      footer.append(priceRow);

      const soldOut = stockOf(item) === 0;
      const alreadyReviewed = state.myReviews.some((review) => review.item_id === item.id);
      const actions = el("div", "product-actions");
      const buy = button(soldOut ? "Sold out" : "Buy", "small", () => placeOrder(item));
      buy.disabled = soldOut;
      actions.append(buy);

      const review = button(
        alreadyReviewed ? "Reviewed" : "Review",
        "small ghost",
        () => openReview(item)
      );
      review.disabled = alreadyReviewed || !hasOrdered(item);
      if (!alreadyReviewed && !hasOrdered(item)) {
        review.title = "Order this item first to review it.";
      }
      actions.append(review);
      footer.append(actions);

      body.append(footer);
      card.append(body);
      return card;
    })
  );
}

function field(labelText, control, hint) {
  const label = el("label", null, labelText);
  label.append(control);
  if (hint) label.append(el("small", "field-hint", hint));
  return label;
}

function stockOf(item) {
  return item.stock_quantity == null ? null : Number(item.stock_quantity);
}

function hasOrdered(item) {
  return state.myOrders.some(
    (order) => order.item_id === item.id && order.status !== "cancelled"
  );
}

function stockLabel(item) {
  const left = stockOf(item);
  if (left === null) return el("span", "stock stock-untracked", "In stock");
  if (left === 0) return el("span", "stock stock-out", "Out of stock");
  if (left <= LOW_STOCK) return el("span", "stock stock-low", `Only ${left} left`);
  return el("span", "stock", `${left} in stock`);
}

function placeOrder(item) {
  const body = el("div", "checkout");

  const summary = el("div", "checkout-item");
  const img = thumbnail(item, "checkout-thumb");
  if (img) summary.append(img);
  const meta = el("div", "checkout-meta");
  meta.append(el("strong", null, item.name));
  meta.append(el("span", "muted", item.store?.name || "Store"));
  meta.append(el("span", "muted", `${money(item.price)} each`));
  summary.append(meta);
  body.append(summary);

  const available = stockOf(item);
  const qty = el("input");
  qty.type = "number";
  qty.min = "1";
  qty.max = String(available === null ? 1000 : Math.min(available, 1000));
  qty.step = "1";
  qty.value = "1";
  qty.name = "quantity";

  const address = el("textarea");
  address.rows = 3;
  address.maxLength = 300;
  address.name = "delivery_address";
  address.value = state.profile?.formatted_address || "";
  address.placeholder = "House / street / area, city, PIN";

  const phone = el("input");
  phone.type = "tel";
  phone.inputMode = "numeric";
  phone.maxLength = 10;
  phone.name = "contact_phone";
  phone.value = state.profile?.phone || "";
  phone.placeholder = "10-digit mobile number";

  body.append(
    field("Quantity", qty, available === null ? undefined : `${available} available.`)
  );
  body.append(field("Delivery address", address, "The shop needs this to deliver."));
  body.append(field("Contact phone", phone));

  const totalRow = el("div", "checkout-total");
  const totalValue = el("strong", null, money(item.price));
  totalRow.append(el("span", null, "Order total"), totalValue);
  body.append(totalRow);

  const error = el("p", "modal-error");
  error.hidden = true;
  body.append(error);

  const recalc = () => {
    const n = Number(qty.value);
    totalValue.textContent =
      Number.isInteger(n) && n > 0 ? money(item.price * n) : "—";
  };
  qty.addEventListener("input", recalc);

  const cancel = button("Cancel", "ghost", () => closeModal());
  const confirm = button("Place order", "", async () => {
    const quantity = Number(qty.value);
    if (!Number.isInteger(quantity) || quantity < 1) {
      error.textContent = "Quantity must be a whole number of at least 1.";
      error.hidden = false;
      return;
    }
    if (available !== null && quantity > available) {
      error.textContent =
        available === 0
          ? "This item is out of stock."
          : `Only ${available} left in stock.`;
      error.hidden = false;
      return;
    }
    if (!address.value.trim()) {
      error.textContent = "A delivery address is required.";
      error.hidden = false;
      address.focus();
      return;
    }
    const phoneCheck = validatePhone(phone.value);
    if (!phone.value.trim()) {
      error.textContent = "A contact phone number is required.";
      error.hidden = false;
      phone.focus();
      return;
    }
    if (!phoneCheck.valid) {
      error.textContent = phoneCheck.error;
      error.hidden = false;
      phone.focus();
      return;
    }

    const originalLabel = confirm.textContent;
    confirm.disabled = true;
    confirm.textContent = "Placing order…";
    try {
      const order = await request(`/item/${item.id}/order`, {
        method: "POST",
        body: JSON.stringify({
          quantity,
          delivery_address: address.value.trim(),
          contact_phone: phoneCheck.value,
        }),
      });
      closeModal();
      setAlert(`Order ${order.reference} placed — ${money(order.total)}.`, "success");
      await loadCustomerData();
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
      confirm.disabled = false;
      confirm.textContent = originalLabel;
    }
  });

  openModal({
    title: `Order ${item.name}`,
    body,
    actions: [cancel, confirm],
    onOpen: () => qty.focus(),
  });
}

function openReview(item) {
  const body = el("div", "review-form");

  const stars = el("div", "star-picker");
  let chosen = 5;
  const buttons = [1, 2, 3, 4, 5].map((value) => {
    const star = el("button", "star-button", "★");
    star.type = "button";
    star.setAttribute("aria-label", `${value} star${value === 1 ? "" : "s"}`);
    star.addEventListener("click", () => {
      chosen = value;
      buttons.forEach((b, i) => b.classList.toggle("on", i < value));
    });
    stars.append(star);
    return star;
  });
  buttons.forEach((b) => b.classList.add("on"));

  const comment = el("textarea");
  comment.rows = 4;
  comment.maxLength = 500;
  comment.placeholder = "What did you think? (optional)";

  body.append(field("Your rating", stars));
  body.append(field("Comment", comment));

  const error = el("p", "modal-error");
  error.hidden = true;
  body.append(error);

  const cancel = button("Cancel", "ghost", () => closeModal());
  const submit = button("Post review", "", async () => {
    submit.disabled = true;
    try {
      await request(`/item/${item.id}/review`, {
        method: "POST",
        body: JSON.stringify({
          rating: chosen,
          comment: comment.value.trim() || undefined,
        }),
      });
      closeModal();
      setAlert("Review posted.", "success");
      await loadCustomerData();
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
      submit.disabled = false;
    }
  });

  openModal({ title: `Review ${item.name}`, body, actions: [cancel, submit] });
}

function orderItemCell(order) {
  const wrap = el("div", "cell-media");
  const item = order.item || {};
  const img = thumbnail(item, "cell-thumb");
  wrap.append(img || el("span", "cell-thumb placeholder", "—"));
  const meta = el("div", "cell-meta");
  meta.append(el("strong", null, item.name || `Item #${order.item_id}`));
  meta.append(el("span", "muted", order.store_name || ""));
  wrap.append(meta);
  return wrap;
}

function orderTotalCell(order) {
  if (order.total === null || order.total === undefined) {
    return el("span", "muted", "unavailable");
  }
  return el("strong", null, money(order.total));
}

const TRANSITION_BUTTON_LABEL = {
  accepted: "Accept",
  packed: "Mark packed",
  out_for_delivery: "Out for delivery",
  completed: "Mark delivered",
  cancelled: "Cancel",
};

async function transitionOrder(order, targetStatus, button, refresh) {
  const originalLabel = button.textContent;
  button.disabled = true;
  button.textContent = "…";
  try {
    const updated = await request(`/order/${order.id}/transition`, {
      method: "POST",
      body: JSON.stringify({ status: targetStatus }),
    });
    setAlert(`${updated.reference} → ${STATUS_LABELS[targetStatus] || targetStatus}.`, "success");
    await refresh();
  } catch (error) {
    setAlert(error.message, "error");
    button.disabled = false;
    button.textContent = originalLabel;
  }
}

function orderActionButtons(order, as, refresh) {
  const wrap = el("div", "row-actions");
  wrap.append(button("Details", "small ghost", () => showOrderDetail(order)));

  const options = order.allowed_next || {};
  Object.entries(options).forEach(([target, actor]) => {
    if (actor !== "either" && actor !== as) return;

    const label = TRANSITION_BUTTON_LABEL[target] || target;
    const dangerous = target === "cancelled";

    const actionButton = button(label, `small ${dangerous ? "danger" : ""}`, async () => {
      if (dangerous) {
        const ok = await confirmAction({
          title: "Cancel this order?",
          message: `${order.reference} — ${order.quantity} × ${order.item?.name || "item"}${
            order.total != null ? ` (${money(order.total)})` : ""
          }. This cannot be undone.`,
          confirmLabel: "Cancel order",
          danger: true,
        });
        if (!ok) return;
      }
      await transitionOrder(order, target, actionButton, refresh);
    });
    wrap.append(actionButton);
  });

  return wrap;
}

function renderMyOrders() {
  const orders = state.myOrders;

  els.ordersTotalCount.textContent = orders.length;
  els.ordersPendingCount.textContent = orders.filter((o) => o.status !== "completed" && o.status !== "cancelled").length;
  els.ordersFulfilledCount.textContent = orders.filter((o) => o.status === "completed").length;
  els.ordersTotalSpent.textContent = money(
    orders
      .filter((o) => o.status !== "cancelled")
      .reduce((sum, o) => sum + (o.total || 0), 0)
  );

  renderTable(
    els.myOrdersTable,
    [
      { label: "Order", value: (order) => el("code", "order-ref", order.reference), className: "col-ref" },
      { label: "Item", value: orderItemCell },
      { label: "Price", value: (order) => (order.unit_price == null ? "—" : money(order.unit_price)), className: "col-num" },
      { label: "Qty", value: (order) => order.quantity, className: "col-num" },
      { label: "Total", value: orderTotalCell, className: "col-num" },
      { label: "Status", value: (order) => statusPill(order.status) },
      { label: "Placed", value: (order) => new Date(order.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) },
      {
        label: "Actions",
        className: "col-actions",
        value: (order) => orderActionButtons(order, "customer", loadCustomerData),
      },
    ],
    orders,
    "You have not ordered anything yet."
  );
}

function showOrderDetail(order) {
  const body = el("div", "order-detail");

  const head = el("div", "checkout-item");
  const img = thumbnail(order.item || {}, "checkout-thumb");
  if (img) head.append(img);
  const meta = el("div", "checkout-meta");
  meta.append(el("strong", null, order.item?.name || `Item #${order.item_id}`));
  meta.append(el("span", "muted", order.store_name || ""));
  head.append(meta);
  body.append(head);

  const rows = [
    ["Order number", order.reference],
    ["Placed", new Date(order.created_at).toLocaleString()],
    ["Status", STATUS_LABELS[order.status] || order.status],
    ["Last updated", order.updated_at ? new Date(order.updated_at).toLocaleString() : "—"],
    ["Unit price", order.unit_price == null ? "—" : money(order.unit_price)],
    ["Quantity", String(order.quantity)],
    ["Total", order.total == null ? "unavailable" : money(order.total)],
    ["Deliver to", order.delivery_address || "Not provided"],
    ["Contact", order.contact_phone || "Not provided"],
  ];
  if (order.username) rows.splice(4, 0, ["Customer", order.username]);

  const list = el("dl", "detail-list");
  rows.forEach(([term, value]) => {
    list.append(el("dt", null, term));
    list.append(el("dd", null, value));
  });
  body.append(list);

  body.append(
    el(
      "p",
      "modal-note",
      "Prices are recorded when the order is placed, so later price changes in the shop do not affect this total."
    )
  );

  openModal({
    title: order.reference,
    body,
    actions: [button("Close", "ghost", () => closeModal())],
  });
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

function renderAccount() {
  const rows = [
    ["Username", state.username || "—"],
    ["Account type", state.isAdmin ? "Admin" : state.role || "—"],
    ["Account reference", state.publicRef || "—"],
    ["Orders placed", String(state.myOrders.length)],
    ["Reviews written", String(state.myReviews.length)],
  ];
  els.accountDetails.replaceChildren();
  rows.forEach(([term, value]) => {
    els.accountDetails.append(el("dt", null, term));
    els.accountDetails.append(el("dd", null, value));
  });

  const profile = state.profile || {};
  ["address_line1", "address_line2", "city", "state", "pincode", "phone"].forEach((name) => {
    const input = els.deliveryForm.querySelector(`[name="${name}"]`);
    if (input) input.value = profile[name] || "";
  });
}

const deliveryFormValidation = bindAddressValidation(els.deliveryForm);

els.deliveryForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const values = deliveryFormValidation.getValues();
  if (!values) return;

  const submitButton = els.deliveryForm.querySelector("button[type=submit]");
  const originalLabel = submitButton.textContent;
  submitButton.disabled = true;
  submitButton.textContent = "Saving…";
  try {
    state.profile = await request("/me/profile", {
      method: "PUT",
      body: JSON.stringify(values),
    });
    setAlert("Delivery details saved. They'll be filled in at checkout.", "success");
  } catch (error) {
    setAlert(error.message, "error");
  } finally {
    submitButton.disabled = false;
    submitButton.textContent = originalLabel;
  }
});

async function loadProfile() {
  try {
    state.profile = await request("/me/profile");
  } catch {
    state.profile = null;
  }
}

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
  const ok = await confirmAction({
    title: "Delete this store?",
    message: `"${store.name}" and all of its items, tags and order history will be removed. This cannot be undone.`,
    confirmLabel: "Delete store",
    danger: true,
  });
  if (!ok) return;
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
        label: "Stock",
        value: (item) => {
          const left = stockOf(item);
          if (left === null) return el("span", "muted", "untracked");
          if (left === 0) return el("span", "stock stock-out", "0");
          return el("span", left <= LOW_STOCK ? "stock stock-low" : null, String(left));
        },
        className: "col-num",
      },
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

function editItem(item) {
  const body = el("div", "checkout");

  const name = el("input");
  name.type = "text";
  name.maxLength = 80;
  name.value = item.name || "";

  const price = el("input");
  price.type = "number";
  price.min = "0";
  price.step = "0.01";
  price.value = item.price ?? "";

  const stock = el("input");
  stock.type = "number";
  stock.min = "0";
  stock.step = "1";
  stock.value = item.stock_quantity ?? "";
  stock.placeholder = "Unlimited";

  const imageUrl = el("input");
  imageUrl.type = "url";
  imageUrl.value = item.image_url || "";
  imageUrl.placeholder = "https://…";

  body.append(field("Item name", name));
  body.append(
    field(
      "Price",
      price,
      "Changing this affects future orders only — past orders keep the price paid."
    )
  );
  body.append(field("Stock", stock, "Leave blank to stop tracking stock for this item."));
  body.append(field("Image URL", imageUrl, "Leave blank for no image."));

  const error = el("p", "modal-error");
  error.hidden = true;
  body.append(error);

  const cancel = button("Cancel", "ghost", () => closeModal());
  const save = button("Save changes", "", async () => {
    if (!name.value.trim()) {
      error.textContent = "Name cannot be empty.";
      error.hidden = false;
      return;
    }
    const rawStock = stock.value.trim();
    if (rawStock && (!Number.isInteger(Number(rawStock)) || Number(rawStock) < 0)) {
      error.textContent = "Stock must be a whole number of 0 or more.";
      error.hidden = false;
      return;
    }
    const payload = {
      name: name.value.trim(),
      price: Number(price.value),
      stock_quantity: rawStock === "" ? null : Number(rawStock),
    };
    if (imageUrl.value.trim()) payload.image_url = imageUrl.value.trim();

    save.disabled = true;
    try {
      await request(`/item/${item.id}`, { method: "PUT", body: JSON.stringify(payload) });
      closeModal();
      setAlert("Item updated.", "success");
      await loadShopkeeperData();
    } catch (err) {
      error.textContent = err.message;
      error.hidden = false;
      save.disabled = false;
    }
  });

  openModal({ title: `Edit ${item.name}`, body, actions: [cancel, save] });
}

async function deleteItem(item) {
  const ok = await confirmAction({
    title: "Delete this item?",
    message: `"${item.name}" will be removed from your inventory, along with its reviews and order history.`,
    confirmLabel: "Delete item",
    danger: true,
  });
  if (!ok) return;
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
      { label: "Order", value: (order) => el("code", "order-ref", order.reference), className: "col-ref" },
      { label: "Item", value: orderItemCell },
      { label: "Customer", value: (order) => order.username || `User #${order.user_id}` },
      {
        label: "Deliver to",
        value: (order) => {
          if (!order.delivery_address) return el("span", "muted", "not provided");
          const wrap = el("div", "cell-meta");
          const line = el("span", "address-line", order.delivery_address);
          line.title = order.delivery_address;
          wrap.append(line);
          if (order.contact_phone) wrap.append(el("span", "muted", order.contact_phone));
          return wrap;
        },
      },
      { label: "Qty", value: (order) => order.quantity, className: "col-num" },
      { label: "Total", value: orderTotalCell, className: "col-num" },
      { label: "Status", value: (order) => statusPill(order.status) },
      { label: "Placed", value: (order) => new Date(order.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short" }) },
      {
        label: "Actions",
        className: "col-actions",
        value: (order) => orderActionButtons(order, "shop", loadStoreOrders),
      },
    ],
    state.storeOrders,
    "No orders for this store yet."
  );
}

function renderFeedback() {
  const data = state.feedback;
  if (!data) return;

  els.feedbackAverage.textContent = Number(data.average_rating).toFixed(2);
  els.feedbackStars.replaceChildren(starNode(data.average_rating));
  els.feedbackCount.textContent = data.review_count
    ? `${data.review_count} review${data.review_count === 1 ? "" : "s"}`
    : "no reviews";

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

function renderUsers() {
  renderTable(
    els.usersTable,
    [
      { label: "User", value: (user) => user.username },
      { label: "Role", value: (user) => el("span", `role-badge role-${user.role}`, user.role) },
      { label: "Admin", value: (user) => (user.is_admin ? "yes" : "—") },
      {
        label: "Status",
        value: (user) => accountStatusPill(user.is_banned),
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
    loadProfile(),
  ]);
  state.items = items || [];
  state.stores = stores || [];
  state.myOrders = orders || [];

  state.myReviews = state.items
    .flatMap((item) => item.reviews || [])
    .filter((review) => review.user_id === state.userId);

  renderCatalogue();
  renderMyOrders();
  renderMyReviews();
  renderAccount();
}

async function loadShopkeeperData() {
  const [items, stores] = await Promise.all([request("/item"), request("/store")]);
  state.items = items || [];
  state.stores = stores || [];

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
  try {
    const me = await request("/me");
    storeSession({
      id: me.id,
      role: me.role,
      username: me.username,
      is_admin: me.is_admin,
    });
    state.publicRef = me.public_ref;
  } catch {
    clearSession();
    showAuthGate();
    return;
  }

  showConsole();
  await loadData();
  setView(location.hash.replace("#", ""));
}

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
      ...(data.stock_quantity?.trim() ? { stock_quantity: Number(data.stock_quantity) } : {}),
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

setAuthRole("customer");
if (state.accessToken) {
  enterConsole();
} else {
  showAuthGate();
}
