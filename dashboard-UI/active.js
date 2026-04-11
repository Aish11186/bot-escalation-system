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
    const data = await response.json()
    complaints = data.complaints || []
    renderComplaints()
} catch (error) {
    grid.innerHTML = `<div class="card"><div class="value">Unable to load active complaints.</div></div>`
}
}

async function resolveComplaint(id) {
try {
    await fetch("/api/complaints/resolve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id })
    })

    complaints = complaints.filter((complaint) => complaint.id !== id)
    renderComplaints()
} catch (error) {
    alert("Unable to resolve the complaint right now.")
}
}

loadComplaints()
setInterval(loadComplaints, 3000)
