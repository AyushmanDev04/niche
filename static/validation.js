const PHONE_REGEX = /^[6-9]\d{9}$/;
const PINCODE_REGEX = /^[1-9]\d{5}$/;

function validatePhone(value) {
  const trimmed = (value || "").trim();
  if (!trimmed) return { valid: true, value: null };
  if (!PHONE_REGEX.test(trimmed)) {
    return { valid: false, error: "Enter a valid 10-digit mobile number." };
  }
  return { valid: true, value: trimmed };
}

function validatePincode(value) {
  const trimmed = (value || "").trim();
  if (!trimmed) return { valid: true, value: null };
  if (!PINCODE_REGEX.test(trimmed)) {
    return { valid: false, error: "Enter a valid 6-digit PIN code." };
  }
  return { valid: true, value: trimmed };
}

function validateRequiredText(value, { label, maxLength = 150 }) {
  const trimmed = (value || "").trim();
  if (!trimmed) return { valid: false, error: `${label} is required.` };
  if (trimmed.length > maxLength) {
    return { valid: false, error: `${label} must be ${maxLength} characters or fewer.` };
  }
  return { valid: true, value: trimmed };
}

function validateOptionalText(value, { label, maxLength = 150 }) {
  const trimmed = (value || "").trim();
  if (!trimmed) return { valid: true, value: null };
  if (trimmed.length > maxLength) {
    return { valid: false, error: `${label} must be ${maxLength} characters or fewer.` };
  }
  return { valid: true, value: trimmed };
}

function validateAddressForm(fields) {
  const checks = {
    address_line1: validateRequiredText(fields.address_line1, { label: "Address line 1", maxLength: 150 }),
    address_line2: validateOptionalText(fields.address_line2, { label: "Address line 2", maxLength: 150 }),
    city: validateRequiredText(fields.city, { label: "City", maxLength: 80 }),
    state: validateRequiredText(fields.state, { label: "State", maxLength: 80 }),
    pincode: validatePincode(fields.pincode),
    phone: validatePhone(fields.phone),
  };

  if (checks.pincode.valid && !fields.pincode?.trim()) {
    checks.pincode = { valid: false, error: "PIN code is required." };
  }
  if (checks.phone.valid && !fields.phone?.trim()) {
    checks.phone = { valid: false, error: "Phone number is required." };
  }

  const errors = {};
  const values = {};
  for (const [key, result] of Object.entries(checks)) {
    if (result.valid) values[key] = result.value;
    else errors[key] = result.error;
  }

  return Object.keys(errors).length > 0
    ? { valid: false, errors }
    : { valid: true, values };
}

function bindAddressValidation(form) {
  const fieldNames = ["address_line1", "address_line2", "city", "state", "pincode", "phone"];
  const errorNodes = {};

  fieldNames.forEach((name) => {
    const input = form.querySelector(`[name="${name}"]`);
    if (!input) return;
    const errorNode = document.createElement("small");
    errorNode.className = "field-error";
    errorNode.hidden = true;
    input.insertAdjacentElement("afterend", errorNode);
    errorNodes[name] = errorNode;

    input.addEventListener("blur", () => {
      const raw = Object.fromEntries(new FormData(form).entries());
      const result = validateAddressForm(raw);
      const fieldError = result.valid ? undefined : result.errors[name];
      errorNode.textContent = fieldError || "";
      errorNode.hidden = !fieldError;
      input.setAttribute("aria-invalid", String(Boolean(fieldError)));
    });
  });

  function getValues() {
    const raw = Object.fromEntries(new FormData(form).entries());
    const result = validateAddressForm(raw);
    if (result.valid) {
      fieldNames.forEach((name) => {
        if (errorNodes[name]) errorNodes[name].hidden = true;
      });
      return result.values;
    }
    fieldNames.forEach((name) => {
      const node = errorNodes[name];
      if (!node) return;
      const message = result.errors[name];
      node.textContent = message || "";
      node.hidden = !message;
    });
    return null;
  }

  return { getValues };
}
