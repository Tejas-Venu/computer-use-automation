
const $ = (id) => document.getElementById(id);

let currentIntervention = null;
let hasControl = false;
let lastSessionId = null;
let lastScreenshotKey = null;
let screenshotUrl = null;
let refreshBusy = false;

const STEPS = [
  ["enter_member_id", "Enter Member ID"],
  ["submit_search", "Submit Search"],
  ["open_details", "Open Member Details"],
  ["extract_balance", "Extract Savings Balance"],
];

function log(message) {
  const line = document.createElement("div");
  line.textContent =
    `[${new Date().toLocaleTimeString()}] ${message}`;

  $("activity").prepend(line);
}

async function api(path, method = "GET", body = null) {
  const headers = {
    "X-Operator-Token": $("token").value,
  };

  if (body !== null) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(path, {
    method,
    headers,
    body: body === null ? undefined : JSON.stringify(body),
    cache: "no-store",
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status}: ${detail}`);
  }

  return response.json();
}

function setEmptyBrowser() {
  $("browserEmpty").hidden = false;
  $("browserImage").hidden = true;
  $("browserUrl").textContent = "No active browser session";
  $("browserStatus").textContent = "Disconnected";
  $("previewLabel").textContent = "Waiting for browser session";
  lastScreenshotKey = null;
}

function updateTimeline(status) {
  const timeline = $("timeline");
  timeline.replaceChildren();

  const currentIndex = STEPS.findIndex(
    ([id]) => id === status.current_step
  );

  const completed =
    status.state === "completed" &&
    status.result?.status === "success";

  const active =
    ["running", "paused", "human_control", "resuming"]
      .includes(status.state);

  STEPS.forEach(([id, label], index) => {
    const item = document.createElement("div");
    item.className = "timeline-item";

    const dot = document.createElement("span");
    dot.className = "timeline-dot";

    const content = document.createElement("div");
    const heading = document.createElement("strong");
    const description = document.createElement("small");

    heading.textContent = label;

    if (completed) {
      item.classList.add("done");
      description.textContent = "Completed";
    } else if (active && currentIndex >= 0) {
      if (index < currentIndex) {
        item.classList.add("done");
        description.textContent = "Completed";
      } else if (index === currentIndex) {
        item.classList.add("current");
        description.textContent =
          status.state === "paused" ||
          status.state === "human_control"
            ? "Awaiting intervention"
            : "In progress";
      } else {
        description.textContent = "Pending";
      }
    } else {
      description.textContent = "Pending";
    }

    content.append(heading, description);
    item.append(dot, content);
    timeline.append(item);
  });
}

async function refreshScreenshot() {
  if (!$("token").value) return;

  const response = await fetch("/api/screenshot", {
    headers: {
      "X-Operator-Token": $("token").value,
    },
    cache: "no-store",
  });

  if (!response.ok) return;

  const blob = await response.blob();
  const newUrl = URL.createObjectURL(blob);

  const image = $("browserImage");

  image.onload = () => {
    if (screenshotUrl) {
      URL.revokeObjectURL(screenshotUrl);
    }

    screenshotUrl = newUrl;
  };

  image.src = newUrl;
  image.hidden = false;
  $("browserEmpty").hidden = true;

  $("previewLabel").textContent =
    `Updated ${new Date().toLocaleTimeString()}`;
}

async function refreshStatus() {
  if (!$("token").value || refreshBusy) return;

  refreshBusy = true;

  try {
    const status = await api("/api/status");

    $("stateBadge").textContent = status.state;
    $("sessionState").textContent = status.state;
    $("sessionOwner").textContent = status.owner || "None";
    $("currentStep").textContent =
      status.current_step || "—";
    $("resultStatus").textContent =
      status.result?.status || "In progress";

    currentIntervention =
      status.interventions?.find(
        (item) =>
          item.status === "pending" ||
          item.status === "in_progress"
      ) || null;

    const operatorId = $("operatorId").value;

    hasControl =
      status.state === "human_control" &&
      status.owner === operatorId;

    $("takeBtn").disabled =
      !currentIntervention ||
      currentIntervention.status !== "pending";

    $("resumeBtn").disabled = !hasControl;
    $("executeBtn").disabled = !hasControl;

    if (currentIntervention) {
      $("interventionTitle").textContent =
        "Operator assistance required";

      $("interventionText").textContent =
        `${currentIntervention.step_id}: ` +
        currentIntervention.reason;
    } else {
      $("interventionTitle").textContent =
        "No intervention required";

      $("interventionText").textContent =
        "Automation is operating normally.";
    }

    updateTimeline(status);

    if (!status.session_id) {
      setEmptyBrowser();
      return;
    }

    $("browserStatus").textContent =
      status.state === "human_control"
        ? "Human Control"
        : "Connected";

    $("browserUrl").textContent =
      status.browser_url || "Mock banking session";

    const isActive = [
      "running",
      "paused",
      "human_control",
      "resuming",
    ].includes(status.state);

    const screenshotKey =
      `${status.session_id}:${status.state}:` +
      `${status.current_step || ""}`;

    if (
      isActive ||
      lastSessionId !== status.session_id ||
      lastScreenshotKey !== screenshotKey
    ) {
      await refreshScreenshot();
      lastScreenshotKey = screenshotKey;
    }

    lastSessionId = status.session_id;
  } catch (error) {
    log(`Status error: ${error.message}`);
  } finally {
    refreshBusy = false;
  }
}


$("startBtn").onclick = async () => {
  try {
    await api("/api/start", "POST", {
      member_id: $("memberId").value,
      demo_intervention: $("demoIntervention").checked,
    });

    log("Automation started.");
    await refreshStatus();
  } catch (error) {
    log(`Start failed: ${error.message}`);
  }
};


$("takeBtn").onclick = async () => {
  if (!currentIntervention) return;

  try {
    await api(
      `/api/interventions/${currentIntervention.intervention_id}/acquire`,
      "POST",
      { operator_id: $("operatorId").value }
    );

    log("Human control acquired.");
    await refreshStatus();
  } catch (error) {
    log(`Takeover failed: ${error.message}`);
  }
};

$("resumeBtn").onclick = async () => {
  if (!currentIntervention) return;

  try {
    await api(
      `/api/interventions/${currentIntervention.intervention_id}/resolve`,
      "POST",
      { operator_id: $("operatorId").value }
    );

    log("Control released. Automation resuming.");
    await refreshStatus();
  } catch (error) {
    log(`Resume failed: ${error.message}`);
  }
};

$("executeBtn").onclick = async () => {
  try {
    const strategy = $("strategy").value;

    const target =
      strategy === "role"
        ? {
            strategy: "role",
            role: $("role").value,
            name: $("accessibleName").value,
          }
        : {
            strategy: "attribute",
            tag: $("tag").value,
            attribute: $("attribute").value,
            value: $("attributeValue").value,
          };

    await api("/api/action", "POST", {
      operator_id: $("operatorId").value,
      action: $("actionType").value,
      target,
      value:
        $("actionType").value === "fill"
          ? $("actionValue").value
          : null,
    });

    log("Manual browser action executed.");
    await refreshStatus();
  } catch (error) {
    log(`Manual action failed: ${error.message}`);
  }
};

$("refreshBrowser").onclick = async () => {
  try {
    await refreshScreenshot();
  } catch (error) {
    log(`Preview refresh failed: ${error.message}`);
  }
};

$("token").addEventListener("change", refreshStatus);
$("operatorId").addEventListener("change", refreshStatus);

setEmptyBrowser();
setInterval(refreshStatus, 2000);
