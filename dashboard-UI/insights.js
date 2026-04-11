const ctx = document.getElementById("chart");

new Chart(ctx, {

type: "bar",

data: {
labels: [
"Returns Issues",
"Refund Issues",
"Complaint Issues"
],

datasets: [{
label: "Bot Failure Count",

data: [400, 250, 380],

backgroundColor: [
"#3b4048",
"#4a5059",
"#5a616b"
],

borderRadius: 6
}]
},

options: {

plugins: {
legend: {
display: false
}
},

scales: {

x: {
ticks: {
color: "#e6e8eb"
},
grid: {
display:false
}
},

y: {
ticks: {
color: "#e6e8eb"
},
grid: {
color:"#2a2f37"
}
}

}

}

});