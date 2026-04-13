const grid = document.getElementById("complaintsGrid")

let complaints = []

function renderComplaints() {
grid.innerHTML = ""

if (!complaints.length) {
    grid.innerHTML = `<div class="card"><div class="value">No active complaints right now.</div></div>`
    return
}

complaints.forEach((complaint) => {
    const card = document.createElement("div")
    card.className = "card"

    card.innerHTML = `
    <div class="label">Issue ID</div>
    <div class="value">${complaint.id}</div>

    <div class="label">Confidence Score</div>
    <div class="value">${complaint.confidence}</div>

    <div class="label">Reason</div>
    <div class="value">${complaint.reason || complaint.complaint || "No reason recorded."}</div>

    <div class="label">Issue</div>
    <div class="value">${complaint.issue || "No issue recorded."}</div>

    <div class="label">Escalation Reason</div>
    <div class="value">${complaint.escalation_reason || "No escalation reason recorded."}</div>

    <div class="label">Last Customer Message</div>
    <div class="value">${complaint.last_customer_message || "No customer message recorded."}</div>

    ${complaint.order_id ? `
    <div class="label">Order ID</div>
    <div class="value">${complaint.order_id}</div>
    ` : ""}

    <button class="btn" data-id="${complaint.id}">
    Connect via Call
    </button>
    `

    card.querySelector("button").addEventListener("click", () => resolveComplaint(complaint.id))
    grid.appendChild(card)
})
}

async function loadComplaints() {
try {
    const response = await fetch("/api/complaints/active")
    if (!response.ok) {
        throw new Error(`Active complaints request failed with ${response.status}`)
    }
    const data = await response.json()
    complaints = data.complaints || []
    renderComplaints()
} catch (error) {
    console.error("Failed to load active complaints:", error)
    grid.innerHTML = `<div class="card"><div class="value">Unable to load active complaints.</div></div>`
}
}

async function resolveComplaint(id) {
try {
    const response = await fetch("/api/complaints/resolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id })
    })
    if (!response.ok) {
        throw new Error(`Resolve complaint request failed with ${response.status}`)
    }

    complaints = complaints.filter((complaint) => complaint.id !== id)
    renderComplaints()
} catch (error) {
    console.error("Failed to resolve complaint:", error)
    alert("Unable to resolve the complaint right now.")
}
}

loadComplaints()
setInterval(loadComplaints, 3000)
