// Utility: General Odoo RPC Fetch
async function fetchOdooRPC({ model, method, kwargs = {}, args = [] }) {
  const payload = {
    id: 1,
    jsonrpc: "2.0",
    method: "call",
    params: {
      model,
      method,
      args,
      kwargs,
    },
  };

  const response = await fetch("/web/dataset/call_kw/", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return response.json();
}

// Utility: Clear and fill a <select> element
function updateSelectOptions(selectEl, options = []) {
  selectEl.innerHTML = '<option value="" selected disabled></option>';
  options.forEach(([key, name]) => {
    const opt = document.createElement("option");
    opt.value = key;
    opt.textContent = name;
    selectEl.appendChild(opt);
  });
}

let userProducts = [];
async function loadUserProducts() {
  try {
    console.log("Starting to load products...");

    const response = await fetch("/my/products/list", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "call",
        params: {},
      }),
    });

    console.log("Response status:", response.status);

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();
    console.log("Raw response data:", data);

    // Kiểm tra cấu trúc response từ Odoo JSON endpoint
    if (data && data.result && data.result.success) {
      userProducts = data.result.products || [];
      console.log("Loaded products:", userProducts);
      refreshAllProductSelects();
    } else if (data && data.success) {
      // Trong trường hợp response trực tiếp
      userProducts = data.products || [];
      console.log("Loaded products (direct):", userProducts);
      refreshAllProductSelects();
    } else {
      console.error(
        "Failed to load products:",
        data.error || data.result?.error || "Unknown error"
      );
      userProducts = [];
    }
  } catch (error) {
    console.error("Error loading products:", error);
    userProducts = [];
  }
}

// Và đảm bảo DOMContentLoaded gọi function này
document.addEventListener("DOMContentLoaded", async function () {
  document.getElementById("department").disabled = true;
  document.getElementById("ticket-type").disabled = true;

  await loadUserProducts();
});

function refreshAllProductSelects() {
  const allSelects = document.querySelectorAll(
    'select[name^="serial_number_"]'
  );

  allSelects.forEach((select) => {
    const currentValue = select.value;
    select.innerHTML = '<option value="" selected disabled></option>';
    userProducts.forEach((product) => {
      const option = document.createElement("option");
      option.value = product.serial_number;
      option.textContent = `${product.serial_number} - ${product.product_name}`;
      select.appendChild(option);
    });

    // Restore previous value if still exists
    if (
      currentValue &&
      userProducts.some((p) => p.serial_number === currentValue)
    ) {
      select.value = currentValue;
    }
  });
}

// Utility: Build product row HTML
function buildProductRowHTML(index) {
  const productOptions = userProducts
    .map(
      (product) =>
        `<option value="${product.serial_number}">${product.serial_number}</option>`
    )
    .join("");
  return `
        <td class="border-table-sale-detail">
            <input list="serialNumbers_${index}"
                   data-index="${index}"
                   name="serial_number_${index}"
                   class="input-gray form-control s_website_form_input add-product-select"
                   placeholder="Tìm số serial…"
                   onchange="onSerialNumberChange(event)" />
            <datalist id="serialNumbers_${index}">
                ${productOptions}
            </datalist>
        </td>
        <td class="border-table-sale-detail">
            <input type="text" data-index="${index}" name="product_name_${index}"
                   class="form-control s_website_form_input" readonly />
        </td>
        <td class="border-table-sale-detail image-cell">
            <div class="image-cell-wrap form-group s_website_form_field s_website_form_custom" data-type="binary" data-name="Field">
                <div class="s_col_no_resize s_col_no_bgcolor">
                    <div class="col-sm form-control attachment-zone">
                        <div class="o_files_preview gx-1">
                            <label class="attachment-label" for="product-attachment-${index}">
                                <span class="img_add_btn"></span>
                            </label>
                        </div>
                        <input id="product-attachment-${index}" type="file"
                               data-index="${index}" name="product_attachment"
                               accept="image/*" multiple style="display:none"
                               onchange="onImgInputChange(event)" />
                    </div>
                </div>
                <br/>
            </div>
        </td>
        <td class="border-table-sale-detail">
            <textarea type="text" data-index="${index}" name="error_description_${index}"
                   class="input-gray form-control s_website_form_input"></textarea>
        </td>
        <td class="border-table-sale-detail">
            <textarea name="error_note_${index}" data-index="${index}"
                      class="input-gray form-control s_website_form_input"></textarea>
        </td>
        <td class="border-table-sale-detail delete-cell">
            <span class="delete-btn" onclick="deleteProductRow(this)">
                <img alt="trash" src="/dat_website_helpdesk/static/src/icons/trash.svg" />
            </span>
        </td>
    `;
}

// Function to add a new product row
function addProductRow() {
  const tbody = document.querySelector("#product-table tbody");
  const productCountInput = document.querySelector("#product-count");
  const newValue = parseInt(productCountInput.value) + 1;

  const row = document.createElement("tr");
  row.innerHTML = buildProductRowHTML(newValue);
  tbody.appendChild(row);

  productCountInput.value = newValue;
}

// Function to delete a product row
function deleteProductRow(btn) {
  const row = btn.closest("tr");
  row.remove();
  const productCountInput = document.querySelector("#product-count");
  productCountInput.value = parseInt(productCountInput.value) - 1;
}

// Function to handle serial number change
async function onSerialNumberChange(ev) {
  const input = ev.target;
  const serialNumber = input.value;
  const index = input.dataset.index;
  if (!serialNumber || !index) return;

  const productNameEl = document.querySelector(
    `input[name="product_name_${index}"]`
  );
  productNameEl.value = "Loading...";

  const data = await fetchOdooRPC({
    model: "stock.lot",
    method: "web_search_read",
    kwargs: {
      specification: { product_id: { fields: { display_name: {} } } },
      domain: [["name", "=", serialNumber]],
      limit: 1,
    },
  });

  if (data.error || !data.result?.records?.length) {
    productNameEl.value = "Not found";
    return;
  }

  productNameEl.value = data.result.records[0].product_id.display_name;
}

document.addEventListener("DOMContentLoaded", function () {
  document.getElementById("department").disabled = true;
  document.getElementById("ticket-type").disabled = true;
});

async function onBranchChange(ev) {
  const branchId = ev.target.value;
  const departmentEl = document.querySelector(`select[name="department"]`);
  const ticketTypeEl = document.querySelector(`select[name="ticket_type"]`);

  // Reset department và ticket type
  departmentEl.innerHTML = '<option value="" selected disabled></option>';
  ticketTypeEl.innerHTML = '<option value="" selected disabled></option>';

  if (!branchId) {
    departmentEl.disabled = true;
    ticketTypeEl.disabled = true;
    return;
  }

  const data = await fetchOdooRPC({
    model: "hr.department",
    method: "get_portal_selections",
    kwargs: {
      branch_id: branchId,
      context: { lang: "vi_VN" },
    },
  });

  if (data.error || !data.result?.length) {
    departmentEl.disabled = true;
    ticketTypeEl.disabled = true;
    return;
  }

  updateSelectOptions(departmentEl, data.result);
  departmentEl.disabled = false;

  ticketTypeEl.disabled = true;
}

async function onDepartmentChange(ev) {
  const departmentId = ev.target.value;
  const ticketTypeEl = document.querySelector(`select[name="ticket_type"]`);

  ticketTypeEl.innerHTML = '<option value="" selected disabled></option>';

  if (!departmentId) {
    ticketTypeEl.disabled = true;
    return;
  }

  const data = await fetchOdooRPC({
    model: "helpdesk.type",
    method: "get_portal_selections",
    kwargs: {
      department_id: departmentId,
      context: { lang: "vi_VN" },
    },
  });

  if (data.error || !data.result?.length) {
    ticketTypeEl.disabled = true;
    return;
  }

  updateSelectOptions(ticketTypeEl, data.result);
  ticketTypeEl.disabled = false;
}

function visibleElements(ticketTypeCode) {
  document
    .querySelectorAll(`.${ticketTypeCode}_visible`)
    .forEach((el) => el.classList.remove("d-none"));
}

function setRequiredElements(ticketTypeCode) {
  document.querySelectorAll(`.${ticketTypeCode}_required`).forEach((el) => {
    el.querySelector(".mark-required").classList.remove("d-none");
    el.querySelector(".s_website_form_input").required = true;
  });
}

async function onTicketTypeChange(ev) {
  // Hide all dynamic elements first
  document
    .querySelectorAll(`.dynamic_visible`)
    .forEach((el) => el.classList.add("d-none"));
  // Reset all dynamic required elements
  document.querySelectorAll(`.dynamic_required`).forEach((el) => {
    el.querySelector(".mark-required").classList.add("d-none");
    el.querySelector(".s_website_form_input").required = false;
  });

  const ticketTypeCode = ev.target.value;
  if (!ticketTypeCode) return;

  visibleElements(ticketTypeCode);
  setRequiredElements(ticketTypeCode);
}

function onImgDeleteClick(ev) {
  const fileBlockEl = ev.target.closest(".o_file_block");
  const fieldEl = fileBlockEl.closest(".s_website_form_field");
  const fileInputEl = fieldEl.querySelector("input[type=file]");
  const fileDetails = fileBlockEl.fileDetails;

  // Create a new file list containing the remaining files.
  const newFileList = new DataTransfer();
  for (const file of Object.values(fileInputEl.fileList.files)) {
    if (
      file.name !== fileDetails.name ||
      file.size !== fileDetails.size ||
      file.type !== fileDetails.type
    ) {
      newFileList.items.add(file);
    }
  }
  // Update the input lists and remove the file block.
  Object.assign(fileInputEl, {
    fileList: newFileList,
    files: newFileList.files,
  });
  fileBlockEl.remove();
}

function onImgInputChange(ev) {
  const fileInputEl = ev.target;
  const uploadedFiles = fileInputEl.files;
  const parentElementEl = fileInputEl.parentElement;
  const previewZoneEl = parentElementEl.querySelector(".o_files_preview");

  // Create a list to keep track of the files.
  if (!fileInputEl.fileList) {
    fileInputEl.fileList = new DataTransfer();
  }

  // If only one file can be uploaded, delete the previous file.
  if (!fileInputEl.hasAttribute("multiple") && uploadedFiles.length > 0) {
    fileInputEl.fileList = new DataTransfer();
    const fileBlockEl = previewZoneEl.querySelector(".o_file_block");
    if (fileBlockEl) {
      fileBlockEl.remove();
    }
  }

  // Add the uploaded files if they are not already there.
  for (const newFile of uploadedFiles) {
    if (
      ![...fileInputEl.fileList.files].some(
        (file) =>
          newFile.name === file.name &&
          newFile.size === file.size &&
          newFile.type === file.type
      )
    ) {
      fileInputEl.fileList.items.add(newFile);
      const fileDetails = {
        name: newFile.name,
        size: newFile.size,
        type: newFile.type,
      };
      const reader = new FileReader();
      reader.onload = function (e) {
        const fileUrl = e.target.result;

        // If image file, show image preview
        if (newFile.type.startsWith("image/")) {
          const previewBlockEl = document.createElement("div");
          previewBlockEl.classList.add("o_file_block");
          previewBlockEl.innerHTML = `
                        <div class="o_file_wrap">
                            <img class="img_preview d-inline-block" src="${fileUrl}"/>
                            <i class="o_img_delete fa fa-times float-end" onclick="onImgDeleteClick(event)"/>
                        </div>`;
          previewZoneEl.appendChild(previewBlockEl);
          previewBlockEl.fileDetails = fileDetails;
        }
      };
      reader.readAsDataURL(newFile);
    }
  }
  // Update the input files.
  fileInputEl.files = fileInputEl.fileList.files;
}
