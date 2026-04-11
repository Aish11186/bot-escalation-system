const grid = document.getElementById("resolvedGrid")

async function loadResolvedComplaints() {
try {
    const response = await fetch("/api/complaints/resolved")
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
        `

        grid.appendChild(card)
    })
} catch (error) {
    grid.innerHTML = `<div class="card"><div class="value">Unable to load resolved complaints.</div></div>`
}
}

loadResolvedComplaints()
