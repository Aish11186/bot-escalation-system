const grid = document.getElementById("resolvedGrid")

async function loadResolvedComplaints() {
try {
    const response = await fetch("/api/complaints/resolved")
    if (!response.ok) {
        throw new Error(`Resolved complaints request failed with ${response.status}`)
    }
    const data = await response.json()
    const resolved = data.complaints || []

    grid.innerHTML = ""

    if (!resolved.length) {
        grid.innerHTML = `<div class="card"><div class="value">No resolved complaints yet.</div></div>`
        return
    }

    resolved.forEach((complaint) => {
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
        `

        grid.appendChild(card)
    })
} catch (error) {
    console.error("Failed to load resolved complaints:", error)
    grid.innerHTML = `<div class="card"><div class="value">Unable to load resolved complaints.</div></div>`
}
}

loadResolvedComplaints()
setInterval(loadResolvedComplaints, 5000)
