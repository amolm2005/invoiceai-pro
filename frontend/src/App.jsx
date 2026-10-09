const API_BASE_URL = "https://invoiceai-pro-backend-h0gq.onrender.com/api/v1";

async function refreshAccessToken() {
  const refreshToken = localStorage.getItem("refresh_token");

  if (!refreshToken) {
    return null;
  }

  const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      refresh_token: refreshToken,
    }),
  });

  if (!response.ok) {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    return null;
  }

  const data = await response.json();

  localStorage.setItem("access_token", data.access_token);

  if (data.refresh_token) {
    localStorage.setItem("refresh_token", data.refresh_token);
  }

  return data.access_token;
}

async function apiFetch(url, options = {}) {
  let token = localStorage.getItem("access_token");

  const response = await fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
      Authorization: `Bearer ${token}`,
    },
  });

  if (response.status !== 401) {
    return response;
  }

  const newToken = await refreshAccessToken();

  if (!newToken) {
    return response;
  }

  return fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
      Authorization: `Bearer ${newToken}`,
    },
  });
}
import { useEffect, useMemo, useRef, useState } from "react";
import "./App.css";


function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(
    !!localStorage.getItem("access_token")
  );

  const [page, setPage] = useState("dashboard");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const [loginLoading, setLoginLoading] = useState(false);
  const [loginError, setLoginError] = useState("");

  const [invoices, setInvoices] = useState([]);
  const [loadingInvoices, setLoadingInvoices] = useState(false);

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
 
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [sortBy, setSortBy] = useState("default");
  const [currentPage, setCurrentPage] = useState(1);
  const invoicesPerPage = 10;

  const [selectedInvoice, setSelectedInvoice] = useState(null);

  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadError, setUploadError] = useState("");

  const fileInputRef = useRef(null);

  useEffect(() => {
    if (isLoggedIn) {
      loadInvoices();
    }
  }, [isLoggedIn]);

  useEffect(() => {
  setCurrentPage(1);
}, [search, statusFilter, dateFrom, dateTo, sortBy]);

  async function handleLogin(e) {
    e.preventDefault();

    setLoginError("");
    setLoginLoading(true);

    try {
      const response = await apiFetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          password,
          remember_me: rememberMe,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Invalid email or password");
      }

      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);

      setIsLoggedIn(true);
      setPage("dashboard");
    } catch (error) {
      setLoginError(error.message || "Unable to sign in");
    } finally {
      setLoginLoading(false);
    }
  }

  function handleLogout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");

    setIsLoggedIn(false);
    setEmail("");
    setPassword("");
    setPage("dashboard");
  }

async function loadInvoices() {
  const token = localStorage.getItem("access_token");

  if (!token) return;

  setLoadingInvoices(true);

  try {
    const response = await apiFetch(`${API_BASE_URL}/invoices`);

    if (!response.ok) {
      throw new Error("Unable to load invoices");
    }

    const data = await response.json();

    if (Array.isArray(data)) {
      setInvoices(data);
    } else if (Array.isArray(data.items)) {
      setInvoices(data.items);
    } else {
      setInvoices([]);
    }
  } catch (error) {
    console.log("Invoice loading:", error.message);
  } finally {
    setLoadingInvoices(false);
  }
}


  async function handleUpload(event) {
    const file = event.target.files?.[0];

    if (!file) return;

    setUploadMessage("");
    setUploadError("");
    setUploading(true);

    try {
      const token = localStorage.getItem("access_token");

      const formData = new FormData();
      formData.append("file", file);

      const response = await apiFetch(
        `${API_BASE_URL}/invoices/upload`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
          },
          body: formData,
        }
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Invoice upload failed"
        );
      }

      setUploadMessage(
        `Invoice "${file.name}" uploaded successfully. Processing has started.`
      );

      await loadInvoices();
    } catch (error) {
      setUploadError(error.message || "Upload failed");
    } finally {
      setUploading(false);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  const normalizedInvoices = useMemo(() => {
    return invoices.map((invoice, index) => ({
      ...invoice,
      _id:
        invoice.id ||
        invoice.invoice_id ||
        `invoice-${index}`,
      _number:
        invoice.invoice_number ||
        invoice.invoice_no ||
        invoice.number ||
        `INV-${String(index + 1).padStart(4, "0")}`,
     _vendor:
        invoice.vendor ||
        invoice.company_name ||
        invoice.vendor_name_raw ||
        invoice.vendor_name ||
        "Unknown Vendor",
      _date:
        invoice.invoice_date ||
        invoice.date ||
        invoice.created_at ||
        "—",
      _gst:
        invoice.vendor_gst ||
        invoice.gst_number ||
        invoice.gst ||
        "-",

      _dueDate:
        invoice.due_date ||
        invoice.dueDate ||
        "-",
      _amount:
        invoice.total_amount ??
        invoice.amount ??
        invoice.total ??
        0,
      _status:
        invoice.status ||
        invoice.processing_status ||
        "Pending",
    }));
  }, [invoices]);

 const filteredInvoices = useMemo(() => {
   return normalizedInvoices.filter((invoice) => {
     const text = `
       ${invoice._number} ${invoice._vendor}
    ` .toLowerCase();

     const matchesSearch = text.includes(
       search.toLowerCase()
    );

     const matchesStatus =
       statusFilter === "All" ||
       invoice._status.toLowerCase() ===
         statusFilter.toLowerCase();

     const invoiceDate = invoice._date
      ? String(invoice._date).slice(0, 10)
      : "";

     const matchesDateFrom =
      !dateFrom || invoiceDate >= dateFrom;

      const matchesDateTo =
      !dateTo || invoiceDate <= dateTo;

     return (
      matchesSearch &&
      matchesStatus &&
      matchesDateFrom &&
      matchesDateTo
    );
  });
}, [
  normalizedInvoices,
  search,
  statusFilter,
  dateFrom,
  dateTo,
]);



const sortedInvoices = useMemo(() => {
  const sorted = [...filteredInvoices];

  switch (sortBy) {
    case "date-newest":
      return sorted.sort(
        (a, b) =>
          new Date(b._date || 0) -
          new Date(a._date || 0)
      );

    case "date-oldest":
      return sorted.sort(
        (a, b) =>
          new Date(a._date || 0) -
          new Date(b._date || 0)
      );

    case "amount-high":
      return sorted.sort(
        (a, b) =>
          Number(b._amount || 0) -
          Number(a._amount || 0)
      );

    case "amount-low":
      return sorted.sort(
        (a, b) =>
          Number(a._amount || 0) -
          Number(b._amount || 0)
      );

    case "vendor-az":
      return sorted.sort((a, b) =>
        String(a._vendor).localeCompare(
          String(b._vendor)
        )
      );

    default:
      return sorted;
  }
}, [filteredInvoices, sortBy]);

const totalPages = Math.ceil(
  sortedInvoices.length / invoicesPerPage
);

const paginatedInvoices = sortedInvoices.slice(
  (currentPage - 1) * invoicesPerPage,
  currentPage * invoicesPerPage
);

const totalInvoices = filteredInvoices.length;

  const processedInvoices = filteredInvoices.filter((invoice) =>
    ["processed", "completed", "valid", "approved"].includes(
      invoice._status.toLowerCase()
    )
  ).length;

  const pendingInvoices = filteredInvoices.filter((invoice) =>
    ["pending", "processing", "uploaded", "review"].includes(
      invoice._status.toLowerCase()
    )
  ).length;

  const flaggedInvoices = filteredInvoices.filter((invoice) =>
  ["flagged"].includes(invoice._status.toLowerCase())
).length;

  const totalAmount = filteredInvoices.reduce(
    (sum, invoice) => {
      const value = Number(
        String(invoice._amount)
          .replace(/[₹,\s]/g, "")
          .replace(/[^\d.-]/g, "")
      );

      return sum + (Number.isFinite(value) ? value : 0);
    },
    0
  );

  function formatCurrency(value) {
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      maximumFractionDigits: 2,
    }).format(value || 0);
  }

  function formatDate(value) {
    if (!value || value === "—") return "—";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return String(value);
    }

    return date.toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  }

  function getStatusClass(status) {
    const value = String(status).toLowerCase();

    if (
      ["processed", "completed", "valid", "approved"].includes(
        value
      )
    ) {
      return "status-success";
    }

    if (
      ["invalid", "failed", "rejected", "error"].includes(value)
    ) {
      return "status-danger";
    }

    return "status-warning";
  }

  if (!isLoggedIn) {
    return (
      <div className="login-page">
        <div className="login-glow glow-one"></div>
        <div className="login-glow glow-two"></div>

        <div className="login-card">
          <div className="brand large-brand">
            <div className="brand-icon">✦</div>
            <div>
              InvoiceAI <span>Pro</span>
            </div>
          </div>

          <div className="login-heading">
            <div className="eyebrow">SMART INVOICE PLATFORM</div>

            <h1>Welcome back</h1>

            <p>
              Sign in to manage invoices, automate extraction,
              and keep your finance workflow moving.
            </p>
          </div>

          <form onSubmit={handleLogin}>
            <div className="input-group">
              <label>Email address</label>

              <div className="input-wrapper">
                <span>✉</span>

                <input
                  type="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) =>
                    setEmail(e.target.value)
                  }
                  required
                />
              </div>
            </div>

            <div className="input-group">
              <label>Password</label>

              <div className="input-wrapper">
                <span>●</span>

              
              <div className="password-field">
  <input
    type={showPassword ? "text" : "password"}
    placeholder="Enter your password"
    value={password}
    onChange={(e) => setPassword(e.target.value)}
    required
  />

  <button
    type="button"
    className="password-toggle"
    onClick={() => setShowPassword(!showPassword)}
  >
    {showPassword ? "Hide" : "Show"}
  </button>
</div>
              </div>
            </div>

            <div className="remember-row">
              <label className="checkbox-label">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) =>
                    setRememberMe(e.target.checked)
                  }
                />

                <span>Remember me</span>
              </label>

              <button
                type="button"
                className="text-button"
              >
                Forgot password?
              </button>
            </div>

            {loginError && (
              <div className="alert alert-error">
                <span>!</span>
                {loginError}
              </div>
            )}

            <button
              type="submit"
              className="primary-button full-button"
              disabled={loginLoading}
            >
              {loginLoading ? (
                <>
                  <span className="spinner"></span>
                  Signing in...
                </>
              ) : (
                <>
                  Sign in
                  <span>→</span>
                </>
              )}
            </button>
          </form>

          <div className="login-security">
            <span>✓</span>
            Secure JWT authentication
            <span>•</span>
            <span>✓</span>
            Company-isolated data
          </div>

          <div className="login-footer">
            InvoiceAI Pro · Intelligent invoice management
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-icon">✦</div>

          <div>
            InvoiceAI
            <span>Pro</span>
          </div>
        </div>

        <div className="workspace">
          <div className="workspace-avatar">A</div>

          <div>
            <small>WORKSPACE</small>
            <strong>My Company</strong>
          </div>

          <span className="workspace-arrow">⌄</span>
        </div>

        <div className="nav-section">
          <span className="nav-label">MAIN MENU</span>

          <button
            className={
              page === "dashboard"
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() => setPage("dashboard")}
          >
            <span>⌂</span>
            Dashboard
          </button>

          <button
            className={
              page === "invoices"
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() => setPage("invoices")}
          >
            <span>▣</span>
            Invoices

            {pendingInvoices > 0 && (
              <b className="nav-count">
                {pendingInvoices}
              </b>
            )}
          </button>

          <button
            className="nav-item"
            onClick={() => {
              setPage("dashboard");

              setTimeout(() => {
                fileInputRef.current?.click();
              }, 100);
            }}
          >
            <span>↑</span>
            Upload Invoice
          </button>

          <button
            className={
              page === "vendors"
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() => setPage("vendors")}
          >
            <span>♙</span>
            Vendors
          </button>

          <button
            className={
              page === "reports"
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() => setPage("reports")}
          >
            <span>◫</span>
            Reports
          </button>
        </div>

        <div className="nav-section">
          <span className="nav-label">SYSTEM</span>

          <button
            className={
              page === "settings"
                ? "nav-item active"
                : "nav-item"
            }
            onClick={() => setPage("settings")}
          >
            <span>⚙</span>
            Settings
          </button>
        </div>

        <div className="sidebar-bottom">
          <div className="ai-status">
            <div className="status-dot"></div>

            <div>
              <strong>AI Engine</strong>
              <small>Ready to process</small>
            </div>

            <span>●</span>
          </div>

          <button
            className="logout-button"
            onClick={handleLogout}
          >
            <span>↪</span>
            Sign out
          </button>

          <div className="version">
            InvoiceAI Pro v1.0
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div>
            <div className="breadcrumb">
              Workspace
              <span>/</span>
              {page === "dashboard"
                ? "Dashboard"
                : page.charAt(0).toUpperCase() +
                  page.slice(1)}
            </div>

            <h1>
              {page === "dashboard"
                ? "Dashboard"
                : page === "invoices"
                ? "Invoices"
                : page === "vendors"
                ? "Vendors"
                : page === "reports"
                ? "Reports"
                : "Settings"}
            </h1>
          </div>

          <div className="topbar-actions">
            <button
              className="icon-button"
              title="Refresh"
              onClick={loadInvoices}
            >
              ↻
            </button>

            <div className="profile">
              <div className="profile-avatar">A</div>

              <div>
                <strong>Admin</strong>
                <small>Company Admin</small>
              </div>
            </div>
          </div>
        </header>

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          onChange={handleUpload}
          hidden
        />

        {page === "dashboard" && (
          <>
            <section className="welcome-banner">
              <div>
                <div className="eyebrow">OVERVIEW</div>

                <h2>
                  Welcome back 👋
                </h2>

                <p>
                  Here's what's happening with your
                  invoices today.
                </p>
              </div>

              <div className="banner-decoration">
                <div className="orb orb-one"></div>
                <div className="orb orb-two"></div>
                <div className="mini-document">▤</div>
              </div>
            </section>

 
            <section className="stats-grid">
              <div className="stat-card">
                <div className="stat-top">
                  <div className="stat-icon blue">▣</div>

                  <span className="stat-trend">
                    Live
                  </span>
                </div>

                <div className="stat-label">
                  Total invoices
                </div>

                <div className="stat-value">
                  {totalInvoices}
                </div>

                <div className="stat-description">
                  All invoices in workspace
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-top">
                  <div className="stat-icon green">
                    ✓
                  </div>

                  <span className="stat-trend green-text">
                    Processed
                  </span>
                </div>

                <div className="stat-label">
                  Successfully processed
                </div>

                <div className="stat-value">
                  {processedInvoices}
                </div>

                <div className="stat-description">
                  Extracted and validated
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-top">
                  <div className="stat-icon orange">
                    ◷
                  </div>

                  <span className="stat-trend orange-text">
                    Attention
                  </span>
                </div>

                <div className="stat-label">
                  Pending review
                </div>

                <div className="stat-value">
                  {pendingInvoices}
                </div>

                <div className="stat-description">
                  Processing or awaiting review
                </div>
              </div>

              <div className="stat-card">
                <div className="stat-top">
                  <div className="stat-icon purple">
                    ₹
                  </div>

                  <span className="stat-trend">
                    INR
                  </span>
                </div>

                <div className="stat-label">
                  Total invoice value
                </div>

                <div className="stat-value amount">
                  {formatCurrency(totalAmount)}
                </div>

                <div className="stat-description">
                  Combined invoice amount
                </div>
              </div>
            </section>

            <section className="dashboard-grid">
              <div className="upload-card">
                <div className="upload-card-header">
                  <div>
                    <div className="eyebrow">
                      AI DOCUMENT PROCESSING
                    </div>

                    <h2>
                      Upload an invoice
                    </h2>

                    <p>
                      Let InvoiceAI Pro read, extract and
                      organize the important information
                      automatically.
                    </p>
                  </div>

                  <div className="upload-symbol">
                    ↑
                  </div>
                </div>

                <button
                  className="upload-dropzone"
                  onClick={() =>
                    fileInputRef.current?.click()
                  }
                  disabled={uploading}
                >
                  <div className="upload-cloud">
                    ↑
                  </div>

                  <strong>
                    {uploading
                      ? "Uploading invoice..."
                      : "Choose an invoice"}
                  </strong>

                  <span>
                    Drag & drop or click to browse
                  </span>

                  <small>
                    PDF · JPG · JPEG · PNG
                  </small>
                </button>

                {uploadMessage && (
                  <div className="alert alert-success">
                    <span>✓</span>
                    {uploadMessage}
                  </div>
                )}

                {uploadError && (
                  <div className="alert alert-error">
                    <span>!</span>
                    {uploadError}
                  </div>
                )}
              </div>

              <div className="processing-card">
                <div className="card-title-row">
                  <div>
                    <div className="eyebrow">
                      AUTOMATION
                    </div>

                    <h3>
                      Invoice intelligence
                    </h3>
                  </div>

                  <div className="ai-badge">
                    AI
                  </div>
                </div>

                <div className="pipeline">
                  <div className="pipeline-item">
                    <div className="pipeline-icon">
                      ↑
                    </div>

                    <div>
                      <strong>Upload</strong>
                      <small>
                        Secure document intake
                      </small>
                    </div>

                    <span>✓</span>
                  </div>

                  <div className="pipeline-line"></div>

                  <div className="pipeline-item">
                    <div className="pipeline-icon">
                      ✦
                    </div>

                    <div>
                      <strong>OCR & Extraction</strong>
                      <small>
                        AI reads invoice fields
                      </small>
                    </div>

                    <span>✓</span>
                  </div>

                  <div className="pipeline-line"></div>

                  <div className="pipeline-item">
                    <div className="pipeline-icon">
                      ✓
                    </div>

                    <div>
                      <strong>Validation</strong>
                      <small>
                        Check extracted information
                      </small>
                    </div>

                    <span>✓</span>
                  </div>
                </div>

                              <div className="stat-card">
                <div className="stat-top">
                  <div className="stat-icon red">
                    !
                  </div>

                  <span className="stat-trend">
                    Attention
                  </span>
                </div>

                <div className="stat-label">
                  Flagged invoices
                </div>

                <div className="stat-value">
                  {flaggedInvoices}
                </div>

                <div className="stat-description">
                  Duplicate or flagged invoices
                </div>
              </div>
              </div>
            </section>

            <section className="recent-card">
              <div className="section-heading">
                <div>
                  <div className="eyebrow">
                    WORKSPACE ACTIVITY
                  </div>

                  <h2>
                    Recent invoices
                  </h2>
                </div>

                <button
                  className="secondary-button"
                  onClick={() => setPage("invoices")}
                >
                  View all →
                </button>
              </div>

              <InvoiceTable
                invoices={filteredInvoices.slice(0, 5)}
                loading={loadingInvoices}
                onSelect={setSelectedInvoice}
              />
            </section>
          </>
        )}

        {page === "invoices" && (
          <section className="page-card">
            <div className="section-heading">
              <div>
                <div className="eyebrow">
                  DOCUMENT MANAGEMENT
                </div>

                <h2>All invoices</h2>

                <p className="section-subtitle">
                  Search, filter and review your invoices.
                </p>
              </div>

              <button
                className="primary-button"
                onClick={() =>
                  fileInputRef.current?.click()
                }
              >
                + Upload invoice
              </button>
            </div>

            <div className="table-toolbar">
              <div className="search-box">
                <span>⌕</span>

                <input
                  placeholder="Search invoices or vendors..."
                  value={search}
                  onChange={(e) =>
                    setSearch(e.target.value)
                  }
                />
              </div>

           <div className="date-filter">
            <label>From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
            />
          </div>

          <div className="date-filter">
           <label>To</label>
           <input
             type="date"
             value={dateTo}
             onChange={(e) => setDateTo(e.target.value)}
           />
         </div>

              <select
                value={statusFilter}
                onChange={(e) =>
                  setStatusFilter(e.target.value)
                }
              >
                <option>All</option>
                <option>Processed</option>
                <option>Pending</option>
                <option>Flagged</option>
                <option>Failed</option>
              </select>

              <select
  value={sortBy}
  onChange={(e) =>
    setSortBy(e.target.value)
  }
>
  <option value="default">Sort: Default</option>
  <option value="date-newest">Date: Newest</option>
  <option value="date-oldest">Date: Oldest</option>
  <option value="amount-high">Amount: High to Low</option>
  <option value="amount-low">Amount: Low to High</option>
  <option value="vendor-az">Vendor: A-Z</option>
</select>

     
              <button
                className="icon-button"
                onClick={loadInvoices}
              >
                ↻
              </button>
            </div>

            <InvoiceTable
             invoices={paginatedInvoices}
              loading={loadingInvoices}
              onSelect={setSelectedInvoice}
              full
            />
            {totalPages > 1 && (
  <div className="pagination">
    <button
      className="secondary-button"
      disabled={currentPage === 1}
      onClick={() =>
        setCurrentPage((page) => page - 1)
      }
    >
      ← Previous
    </button>

    <div className="pagination-pages">
      {Array.from(
        { length: totalPages },
        (_, index) => index + 1
      ).map((pageNumber) => (
        <button
          key={pageNumber}
          className={
            currentPage === pageNumber
              ? "pagination-page active"
              : "pagination-page"
          }
          onClick={() => setCurrentPage(pageNumber)}
        >
          {pageNumber}
        </button>
      ))}
    </div>

    <button
      className="secondary-button"
      disabled={currentPage === totalPages}
      onClick={() =>
        setCurrentPage((page) => page + 1)
      }
    >
      Next →
    </button>
  </div>
)}

          </section>
        )}

      {page === "vendors" && (
  <VendorPage apiFetch={apiFetch} />
)}

      {page === "reports" && (
  <ReportsPage apiFetch={apiFetch} />
)}

      {page === "settings" && (
  <SettingsPage />
)}
      </main>

      {selectedInvoice && (
        <InvoiceModal
          invoice={selectedInvoice}
          onClose={() => setSelectedInvoice(null)}
        />
      )}
    </div>
  );
}

function InvoiceTable({
  invoices,
  loading,
  onSelect,
  full = false,
}) {
  if (loading) {
    return (
      <div className="table-loading">
        <span className="spinner dark"></span>
        Loading invoices...
      </div>
    );
  }

  if (!invoices.length) {
    return (
      <div className="table-empty">
        <div className="empty-icon">▣</div>

        <h3>No invoices found</h3>

        <p>
          Upload your first invoice to start building
          your workspace.
        </p>
      </div>
    );
  }

  return (
    <div className="table-wrapper">
      <table>
      <thead>
        <tr>
         <th>INVOICE</th>
         <th>VENDOR</th>
         <th>DATE</th>
         <th>GST NUMBER</th>
         <th>DUE DATE</th>
         <th>AMOUNT</th>
         <th>STATUS</th>
      <th></th>
        </tr>
      </thead>

        <tbody>
          {invoices.map((invoice) => (
            <tr
              key={invoice._id}
              onClick={() => onSelect(invoice)}
            >
              <td>
                <div className="invoice-cell">
                  <div className="invoice-file-icon">
                    ▤
                  </div>

                  <div>
                    <strong>{invoice._number}</strong>

                    <small>
                      Invoice document
                    </small>
                  </div>
                </div>
              </td>

              <td>
                <strong className="vendor-name">
                  {invoice._vendor}
                </strong>
              </td>

              <td>
                {formatTableDate(invoice._date)}
              </td>

              <td>
                {invoice._gst}
              </td>

              <td>
                {formatTableDate(invoice._dueDate)}
              </td>

              <td>
                <strong>
                  {formatTableCurrency(
                    invoice._amount
                  )}
                </strong>
              </td>

              <td>
                <span
                  className={`status-badge ${getTableStatusClass(
                    invoice._status
                  )}`}
                >
                  <span></span>
                  {invoice._status}
                </span>
              </td>

              <td>
                <button
                  className="row-arrow"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelect(invoice);
                  }}
                >
                  →
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {!full && invoices.length >= 5 && (
        <div className="table-footer">
          Showing latest invoices
        </div>
      )}
    </div>
  );
}

function InvoiceModal({ invoice, onClose }) {
  const amount = invoice._amount || 0;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className="invoice-modal"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="modal-header">
          <div>
            <div className="eyebrow">
            
            </div>

            <h2>{invoice._number}</h2>
          </div>

          <button
            className="modal-close"
            onClick={onClose}
          >
            ×
          </button>
        </div>

        <div className="modal-status-row">
          <span
            className={`status-badge ${getTableStatusClass(
              invoice._status
            )}`}
          >
            <span></span>
            {invoice._status}
          </span>

          <span className="modal-date">
            {formatTableDate(invoice._date)}
          </span>
        </div>

        <div className="details-grid">
          <DetailItem
            label="Vendor Name"
            value={invoice._vendor}
          />

          <DetailItem
            label="Invoice Number"
            value={invoice._number}
          />

          <DetailItem
            label="Invoice Date"
            value={formatTableDate(invoice._date)}
          />

          <DetailItem
            label="GST Number"
            value={
              invoice._gst ||
              "Not detected"
            }
          />

          <DetailItem
  label="PO Number"
  value={invoice.po_number || "Not detected"}
/>
<DetailItem
  label="PO Amount"
  value={
    invoice.po_amount != null
      ? formatTableCurrency(invoice.po_amount)
      : "Not detected"
  }
/>

         <DetailItem
  label="Payment Terms"
  value={invoice.payment_terms || "Not detected"}
/>

          <DetailItem
  label="Due Date"
  value={formatTableDate(invoice._dueDate)}
/>

          <DetailItem
            label="Subtotal"
           value={
             invoice.invoice_amount != null
               ? formatTableCurrency(invoice.invoice_amount)
               : "Not detected"
          }
          />

          <DetailItem
            label="Total Amount"
            value={formatTableCurrency(amount)}
            highlight
          />
        </div>

        <div className="validation-panel">
          <div className="validation-icon">✓</div>

          <div>
            <strong>Invoice validation</strong>

            <p>
              Invoice data is available for review.
            </p>
          </div>
        </div>

        <button
          className="primary-button full-button"
          onClick={onClose}
        >
          Close details
        </button>
      </div>
    </div>
  );
}

function DetailItem({
  label,
  value,
  highlight = false,
}) {
  return (
    <div className="detail-item">
      <span>{label}</span>

      <strong className={highlight ? "highlight" : ""}>
        {value}
      </strong>
    </div>
  );
}

function formatTableCurrency(value) {
  const number = Number(
    String(value ?? 0)
      .replace(/[₹,\s]/g, "")
      .replace(/[^\d.-]/g, "")
  );

  if (!Number.isFinite(number)) {
    return "₹0.00";
  }

  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(number);
}

function formatTableDate(value) {
  if (!value || value === "—") return "—";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function getTableStatusClass(status) {
  const value = String(status).toLowerCase();

  if (
    ["processed", "completed", "valid", "approved"].includes(
      value
    )
  ) {
    return "table-status-success";
  }

  if (
    ["failed", "invalid", "rejected", "error"].includes(
      value
    )
  ) {
    return "table-status-danger";
  }

  return "table-status-warning";
}

export default App;

function VendorPage({ apiFetch }) {
  const [vendors, setVendors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("All");

  const [selectedVendor, setSelectedVendor] = useState(null);
  const [loadingDetails, setLoadingDetails] = useState(false);

  const loadVendors = async () => {
  try {
    setLoading(true);
    setError("");

    const params = new URLSearchParams();

    if (search.trim()) {
      params.append("search", search.trim());
    }

    if (riskFilter !== "All") {
      params.append("risk_status", riskFilter);
    }

    const query = params.toString();

    const response = await apiFetch(
      `${API_BASE_URL}/vendors${query ? `?${query}` : ""}`
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Failed to load vendors"
      );
    }

    if (Array.isArray(data)) {
      setVendors(data);
    } else {
      setVendors([]);
    }
  } catch (err) {
    console.error("Failed to load vendors:", err);
    setError(err.message || "Failed to load vendors.");
    setVendors([]);
  } finally {
    setLoading(false);
  }
};
  useEffect(() => {
    loadVendors();
  }, [riskFilter]);

  const handleSearch = (event) => {
    event.preventDefault();
    loadVendors();
  };

  const handleVendorClick = async (vendor) => {
  try {
    setLoadingDetails(true);

    const response = await apiFetch(
      `${API_BASE_URL}/vendors/${vendor.id}`
    );

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.detail || "Failed to load vendor details"
      );
    }

    setSelectedVendor(data);
  } catch (err) {
    console.error(
      "Failed to load vendor details:",
      err
    );

    alert(
      err.message ||
        "Failed to load vendor details."
    );
  } finally {
    setLoadingDetails(false);
  }
};

  const totalVendors = vendors.length;

  const normalVendors = vendors.filter(
    (vendor) =>
      String(vendor.risk_status || "").toLowerCase() ===
      "normal"
  ).length;

  const mediumRiskVendors = vendors.filter(
    (vendor) =>
      String(vendor.risk_status || "").toLowerCase() ===
      "medium_risk"
  ).length;

  const highRiskVendors = vendors.filter(
    (vendor) =>
      String(vendor.risk_status || "").toLowerCase() ===
      "high_risk"
  ).length;

  const formatRiskStatus = (status) => {
    if (!status) return "Unknown";

    return String(status)
      .replace(/_/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };

  const getRiskClass = (status) => {
    const value = String(status || "").toLowerCase();

    if (value === "high_risk") {
      return "risk-high";
    }

    if (value === "medium_risk") {
      return "risk-medium";
    }

    if (value === "normal") {
      return "risk-normal";
    }

    return "risk-unknown";
  };

  const formatCurrency = (value) => {
    if (value === null || value === undefined || value === "") {
      return "₹0.00";
    }

    const number = Number(value);

    if (Number.isNaN(number)) {
      return "₹0.00";
    }

    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      minimumFractionDigits: 2,
    }).format(number);
  };

  return (
    <section className="vendors-page">

      {/* PAGE HEADER */}
      <div className="page-header">
        <div>
          <div className="eyebrow">
            VENDOR INTELLIGENCE
          </div>

          <h2>Vendor Management</h2>

          <p>
            Monitor vendor activity, invoice volume and
            vendor risk across your workspace.
          </p>
        </div>

       <button
  className="secondary-button"
  onClick={() => loadVendors()}
>
  ↻ Refresh
</button>
      </div>

      {/* SUMMARY CARDS */}
      <div className="stats-grid vendor-stats">

        <div className="stat-card">
          <div className="stat-icon">♙</div>

          <div>
            <span className="stat-label">
              Total Vendors
            </span>

            <strong className="stat-value">
              {totalVendors}
            </strong>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">✓</div>

          <div>
            <span className="stat-label">
              Normal
            </span>

            <strong className="stat-value">
              {normalVendors}
            </strong>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">!</div>

          <div>
            <span className="stat-label">
              Medium Risk
            </span>

            <strong className="stat-value">
              {mediumRiskVendors}
            </strong>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">⚠</div>

          <div>
            <span className="stat-label">
              High Risk
            </span>

            <strong className="stat-value">
              {highRiskVendors}
            </strong>
          </div>
        </div>

      </div>

      {/* FILTER BAR */}
      <div className="table-toolbar vendor-toolbar">

        <form
          className="search-box"
          onSubmit={handleSearch}
        >
          <span>⌕</span>

          <input
            type="text"
            placeholder="Search vendors..."
            value={search}
            onChange={(event) =>
              setSearch(event.target.value)
            }
          />
        </form>

        <select
          value={riskFilter}
          onChange={(event) =>
            setRiskFilter(event.target.value)
          }
        >
          <option value="All">All Risk Levels</option>
          <option value="normal">Normal</option>
          <option value="medium_risk">
            Medium Risk
          </option>
          <option value="high_risk">
            High Risk
          </option>
        </select>

        <button
          className="primary-button"
          onClick={loadVendors}
        >
          Search
        </button>

      </div>

      {/* ERROR */}
      {error && (
        <div className="upload-error">
          {error}
        </div>
      )}

      {/* TABLE */}
      {loading ? (
        <div className="table-loading">
          <span className="spinner dark"></span>
          Loading vendors...
        </div>
      ) : vendors.length === 0 ? (
        <div className="table-empty">
          <div className="empty-icon">♙</div>

          <h3>No vendors found</h3>

          <p>
            Vendors will appear here after invoices
            are processed.
          </p>
        </div>
      ) : (
        <div className="table-wrapper">

          <table>

            <thead>
              <tr>
                <th>VENDOR</th>
                <th>GST NUMBER</th>
                <th>TOTAL ORDERS</th>
                <th>DELAYED</th>
                <th>RISK SCORE</th>
                <th>RISK STATUS</th>
                <th></th>
              </tr>
            </thead>

            <tbody>
              {vendors.map((vendor) => (
                <tr
                  key={vendor.id}
                  onClick={() =>
                    handleVendorClick(vendor)
                  }
                  style={{ cursor: "pointer" }}
                >

                  <td>
                    <div className="invoice-cell">

                      <div className="invoice-file-icon">
                        ♙
                      </div>

                      <div>
                        <strong>
                          {vendor.name ||
                            "Unknown Vendor"}
                        </strong>

                        <small>
                          Vendor
                        </small>
                      </div>

                    </div>
                  </td>

                  <td>
                    {vendor.gst_number ||
                      vendor.gst ||
                      vendor.vendor_gst ||
                      "—"}
                  </td>

                  <td>
                    {vendor.total_orders ?? 0}
                  </td>

                  <td>
                    {vendor.delayed_deliveries ?? 0}
                  </td>

                  <td>
                    {vendor.risk_score !== null &&
                    vendor.risk_score !== undefined
                      ? Number(vendor.risk_score).toFixed(1)
                      : "—"}
                  </td>

                  <td>
                    <span
                      className={`status-badge ${getRiskClass(
                        vendor.risk_status
                      )}`}
                    >
                      {formatRiskStatus(
                        vendor.risk_status
                      )}
                    </span>
                  </td>

                  <td>
                    <span className="table-arrow">
                      →
                    </span>
                  </td>

                </tr>
              ))}
            </tbody>

          </table>

        </div>
      )}

      {/* VENDOR DETAILS MODAL */}
      {selectedVendor && (
        <div className="modal-backdrop">

          <div className="modal vendor-modal">

            <div className="modal-header">

              <div>
                <div className="eyebrow">
                  VENDOR DETAILS
                </div>

                <h2>
                  {selectedVendor.name ||
                    "Vendor"}
                </h2>
              </div>

              <button
                className="modal-close"
                onClick={() =>
                  setSelectedVendor(null)
                }
              >
                ×
              </button>

            </div>

            {loadingDetails ? (
              <div className="table-loading">
                <span className="spinner dark"></span>
                Loading vendor details...
              </div>
            ) : (
              <div className="vendor-details-grid">

                <div className="detail-card">
                  <span>GST Number</span>

                  <strong>
                    {selectedVendor.gst_number ||
                      selectedVendor.gst ||
                      selectedVendor.vendor_gst ||
                      "Not available"}
                  </strong>
                </div>

                <div className="detail-card">
                  <span>Risk Status</span>

                  <strong>
                    {formatRiskStatus(
                      selectedVendor.risk_status
                    )}
                  </strong>
                </div>

                <div className="detail-card">
                  <span>Risk Score</span>

                  <strong>
                    {selectedVendor.risk_score !== null &&
                    selectedVendor.risk_score !== undefined
                      ? Number(
                          selectedVendor.risk_score
                        ).toFixed(1)
                      : "Not available"}
                  </strong>
                </div>

                <div className="detail-card">
                  <span>Total Orders</span>

                  <strong>
                    {selectedVendor.total_orders ?? 0}
                  </strong>
                </div>

                <div className="detail-card">
                  <span>Delayed Deliveries</span>

                  <strong>
                    {selectedVendor.delayed_deliveries ?? 0}
                  </strong>
                </div>

                <div className="detail-card">
                  <span>On-Time Deliveries</span>

                  <strong>
                    {selectedVendor.on_time_deliveries ?? 0}
                  </strong>
                </div>

                <div className="detail-card">
                  <span>Total Invoice Value</span>

                  <strong>
                    {formatCurrency(
                      selectedVendor.total_invoice_value
                    )}
                  </strong>
                </div>

                <div className="detail-card">
                  <span>Average Delay</span>

                  <strong>
                    {selectedVendor.average_delay_days ??
                      0}{" "}
                    days
                  </strong>
                </div>

              </div>
            )}

            <div className="modal-footer">

              <button
                className="secondary-button"
                onClick={() =>
                  setSelectedVendor(null)
                }
              >
                Close
              </button>

            </div>

          </div>

        </div>
      )}

    </section>
  );
}

function ReportsPage({ apiFetch }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadReport = async () => {
    try {
      setLoading(true);
      setError("");

      const response = await apiFetch(
        `${API_BASE_URL}/dashboard/summary`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Failed to load reports"
        );
      }

      setReport(data);
    } catch (err) {
      console.error("Failed to load reports:", err);
      setError(
        err.message || "Failed to load reports."
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReport();
  }, []);

  const formatCurrency = (value) => {
    const amount = Number(value) || 0;

    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      minimumFractionDigits: 2,
    }).format(amount);
  };

  const formatStatus = (status) => {
    if (!status) return "Unknown";

    return String(status)
      .replace(/_/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  };

  const getStatusClass = (status) => {
    const value = String(status || "").toLowerCase();

    if (value === "processed") {
      return "risk-normal";
    }

    if (
      value === "needs_review" ||
      value === "pending"
    ) {
      return "risk-medium";
    }

    if (value === "flagged") {
      return "risk-high";
    }

    return "risk-unknown";
  };

  if (loading) {
    return (
      <section className="reports-page">
        <div className="table-loading">
          <span className="spinner dark"></span>
          Loading reports...
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="reports-page">
        <div className="upload-error">
          {error}
        </div>

        <button
          className="primary-button"
          onClick={loadReport}
        >
          Try Again
        </button>
      </section>
    );
  }

  if (!report) {
    return null;
  }

  const statusBreakdown =
    report.invoice_status_breakdown || {};

  const monthlyTrend =
    report.monthly_invoice_trend || [];

  const topVendors =
    report.top_vendors || [];

  const worstVendors =
    report.worst_vendors || [];

  const maxMonthlyCount = Math.max(
    ...monthlyTrend.map(
      (item) => Number(item.count) || 0
    ),
    1
  );

  const maxVendorValue = Math.max(
    ...topVendors.map(
      (vendor) => Number(vendor.value) || 0
    ),
    1
  );

  return (
    <section className="reports-page">

      {/* HEADER */}
      <div className="page-header">
        <div>
          <div className="eyebrow">
            BUSINESS INTELLIGENCE
          </div>

          <h2>Reports & Analytics</h2>

          <p>
            Analyze invoice activity, processing
            performance and vendor risk.
          </p>
        </div>

        <button
          className="secondary-button"
          onClick={loadReport}
        >
          ↻ Refresh
        </button>
      </div>

      {/* KPI CARDS */}
      <div className="stats-grid reports-stats">

        <div className="stat-card">
          <div className="stat-icon">
            ▣
          </div>

          <div>
            <span className="stat-label">
              Total Invoices
            </span>

            <strong className="stat-value">
              {report.total_invoices ?? 0}
            </strong>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">
            ₹
          </div>

          <div>
            <span className="stat-label">
              Monthly Invoice Value
            </span>

            <strong className="stat-value">
              {formatCurrency(
                report.monthly_invoice_value
              )}
            </strong>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">
            ✓
          </div>

          <div>
            <span className="stat-label">
              Processed
            </span>

            <strong className="stat-value">
              {report.invoices_processed ?? 0}
            </strong>
          </div>
        </div>

        <div className="stat-card">
          <div className="stat-icon">
            !
          </div>

          <div>
            <span className="stat-label">
              Flagged
            </span>

            <strong className="stat-value">
              {report.flagged_invoices ?? 0}
            </strong>
          </div>
        </div>

      </div>

      {/* SECONDARY METRICS */}
      <div className="reports-metrics">

        <div className="report-metric-card">
          <span>Pending Review</span>
          <strong>
            {report.pending_review ?? 0}
          </strong>
        </div>

        <div className="report-metric-card">
          <span>Duplicate Invoices</span>
          <strong>
            {report.duplicate_invoices ?? 0}
          </strong>
        </div>

        <div className="report-metric-card">
          <span>Total Vendors</span>
          <strong>
            {report.total_vendors ?? 0}
          </strong>
        </div>

        <div className="report-metric-card">
          <span>Risk Vendors</span>
          <strong>
            {report.risk_vendors ?? 0}
          </strong>
        </div>

        <div className="report-metric-card">
          <span>OCR Accuracy</span>
          <strong>
            {report.ocr_accuracy ?? 0}%
          </strong>
        </div>

        <div className="report-metric-card">
          <span>Today's Uploads</span>
          <strong>
            {report.todays_uploads ?? 0}
          </strong>
        </div>

      </div>

      {/* MONTHLY TREND + STATUS */}
      <div className="reports-two-column">

        {/* MONTHLY TREND */}
        <div className="report-card">

          <div className="report-card-header">
            <div>
              <h3>Invoice Activity</h3>
              <p>Last 6 months</p>
            </div>
          </div>

          <div className="monthly-chart">

            {monthlyTrend.length === 0 ? (
              <div className="chart-empty">
                No monthly data available
              </div>
            ) : (
              monthlyTrend.map((item) => {

                const count =
                  Number(item.count) || 0;

                const height =
                  Math.max(
                    (count / maxMonthlyCount) * 100,
                    count > 0 ? 8 : 2
                  );

                return (
                  <div
                    className="chart-column"
                    key={item.month}
                  >

                    <div className="chart-value">
                      {count}
                    </div>

                    <div className="chart-bar-area">

                      <div
                        className="chart-bar"
                        style={{
                          height: `${height}%`,
                        }}
                      />

                    </div>

                    <span className="chart-label">
                      {item.month}
                    </span>

                  </div>
                );
              })
            )}

          </div>

        </div>

        {/* STATUS BREAKDOWN */}
        <div className="report-card">

          <div className="report-card-header">
            <div>
              <h3>Invoice Status</h3>
              <p>Current distribution</p>
            </div>
          </div>

          <div className="status-report-list">

            {Object.keys(statusBreakdown).length === 0 ? (
              <div className="chart-empty">
                No status data available
              </div>
            ) : (
              Object.entries(statusBreakdown).map(
                ([status, count]) => (
                  <div
                    className="status-report-row"
                    key={status}
                  >

                    <div className="status-report-info">

                      <span
                        className={`status-badge ${getStatusClass(
                          status
                        )}`}
                      >
                        {formatStatus(status)}
                      </span>

                      <strong>
                        {count}
                      </strong>

                    </div>

                    <div className="status-report-track">

                      <div
                        className="status-report-fill"
                        style={{
                          width: `${
                            report.total_invoices
                              ? (Number(count) /
                                  report.total_invoices) *
                                100
                              : 0
                          }%`,
                        }}
                      />

                    </div>

                  </div>
                )
              )
            )}

          </div>

        </div>

      </div>

      {/* TOP VENDORS */}
      <div className="report-card">

        <div className="report-card-header">
          <div>
            <h3>Top Vendors by Invoice Value</h3>
            <p>Highest invoice value vendors</p>
          </div>
        </div>

        {topVendors.length === 0 ? (
          <div className="chart-empty">
            No vendor data available
          </div>
        ) : (
          <div className="vendor-report-list">

            {topVendors.map((vendor, index) => {

              const value =
                Number(vendor.value) || 0;

              const width =
                (value / maxVendorValue) * 100;

              return (
                <div
                  className="vendor-report-row"
                  key={`${vendor.name}-${index}`}
                >

                  <div className="vendor-report-name">
                    <span>
                      {index + 1}
                    </span>

                    <strong>
                      {vendor.name ||
                        "Unknown Vendor"}
                    </strong>
                  </div>

                  <div className="vendor-report-bar">

                    <div className="vendor-report-track">
                      <div
                        className="vendor-report-fill"
                        style={{
                          width: `${width}%`,
                        }}
                      />
                    </div>

                    <strong>
                      {formatCurrency(value)}
                    </strong>

                  </div>

                </div>
              );
            })}

          </div>
        )}

      </div>

      {/* RISK VENDORS */}
      <div className="report-card">

        <div className="report-card-header">
          <div>
            <h3>Vendor Risk Overview</h3>
            <p>
              Vendors with the highest recorded
              risk scores
            </p>
          </div>
        </div>

        {worstVendors.length === 0 ? (
          <div className="chart-empty">
            No risk vendor data available
          </div>
        ) : (
          <div className="risk-vendor-table">

            <div className="risk-vendor-header">
              <span>VENDOR</span>
              <span>RISK SCORE</span>
              <span>STATUS</span>
            </div>

            {worstVendors.map((vendor, index) => (
              <div
                className="risk-vendor-row"
                key={`${vendor.name}-${index}`}
              >

                <strong>
                  {vendor.name ||
                    "Unknown Vendor"}
                </strong>

                <span>
                  {vendor.risk_score !== null &&
                  vendor.risk_score !== undefined
                    ? Number(
                        vendor.risk_score
                      ).toFixed(1)
                    : "—"}
                </span>

                <span
                  className={`status-badge ${getStatusClass(
                    vendor.status
                  )}`}
                >
                  {formatStatus(vendor.status)}
                </span>

              </div>
            ))}

          </div>
        )}

      </div>

    </section>
  );
}

function SettingsPage() {
  const [companyName, setCompanyName] = useState("My Company");
  const [adminName, setAdminName] = useState("Admin");
  const [adminEmail, setAdminEmail] = useState("");
  const [saved, setSaved] = useState(false);

  const handleSave = (event) => {
    event.preventDefault();

    setSaved(true);

    setTimeout(() => {
      setSaved(false);
    }, 3000);
  };

  return (
    <section className="settings-page">

      <div className="page-header">
        <div>
          <div className="eyebrow">
            WORKSPACE SETTINGS
          </div>

          <h2>Settings</h2>

          <p>
            Manage your workspace and administrator
            information.
          </p>
        </div>
      </div>

      <form onSubmit={handleSave}>

        {/* COMPANY */}
        <div className="settings-card">

          <div className="settings-card-header">
            <div>
              <h3>Company Profile</h3>

              <p>
                Basic information about your workspace.
              </p>
            </div>
          </div>

          <div className="settings-form-grid">

            <div className="settings-field">
              <label>
                Company Name
              </label>

              <input
                type="text"
                value={companyName}
                onChange={(event) =>
                  setCompanyName(event.target.value)
                }
                placeholder="Enter company name"
              />
            </div>

            <div className="settings-field">
              <label>
                Workspace
              </label>

              <input
                type="text"
                value="My Company"
                disabled
              />
            </div>

          </div>

        </div>

        {/* ADMIN */}
        <div className="settings-card">

          <div className="settings-card-header">
            <div>
              <h3>Administrator Profile</h3>

              <p>
                Information about the current
                workspace administrator.
              </p>
            </div>
          </div>

          <div className="settings-form-grid">

            <div className="settings-field">
              <label>
                Admin Name
              </label>

              <input
                type="text"
                value={adminName}
                onChange={(event) =>
                  setAdminName(event.target.value)
                }
                placeholder="Enter admin name"
              />
            </div>

            <div className="settings-field">
              <label>
                Admin Email
              </label>

              <input
                type="email"
                value={adminEmail}
                onChange={(event) =>
                  setAdminEmail(event.target.value)
                }
                placeholder="Enter admin email"
              />
            </div>

          </div>

        </div>

        {/* SECURITY */}
        <div className="settings-card">

          <div className="settings-card-header">
            <div>
              <h3>Security</h3>

              <p>
                Security-related options for your
                account.
              </p>
            </div>
          </div>

          <div className="settings-security-row">

            <div>
              <strong>
                Password
              </strong>

              <span>
                Your account password is protected
                by authentication.
              </span>
            </div>

            <button
              type="button"
              className="secondary-button"
              onClick={() =>
                alert(
                  "Password change can be connected to the backend later."
                )
              }
            >
              Change Password
            </button>

          </div>

        </div>

        {/* SYSTEM */}
        <div className="settings-card">

          <div className="settings-card-header">
            <div>
              <h3>System Status</h3>

              <p>
                Current InvoiceAI Pro system status.
              </p>
            </div>
          </div>

          <div className="system-status-list">

            <div className="system-status-row">
              <div>
                <strong>
                  Backend API
                </strong>

                <span>
                  FastAPI service
                </span>
              </div>

              <span className="system-online">
                ● Online
              </span>
            </div>

            <div className="system-status-row">
              <div>
                <strong>
                  Database
                </strong>

                <span>
                  PostgreSQL
                </span>
              </div>

              <span className="system-online">
                ● Connected
              </span>
            </div>

            <div className="system-status-row">
              <div>
                <strong>
                  OCR Engine
                </strong>

                <span>
                  Invoice processing engine
                </span>
              </div>

              <span className="system-online">
                ● Ready
              </span>
            </div>

          </div>

        </div>

        {/* SAVE */}
        <div className="settings-actions">

          {saved && (
            <span className="settings-saved">
              ✓ Settings saved
            </span>
          )}

          <button
            type="submit"
            className="primary-button"
          >
            Save Changes
          </button>

        </div>

      </form>

    </section>
  );
}
