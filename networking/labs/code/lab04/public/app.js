// Talks to the server's JSON endpoint: GET and POST /api/guestbook.
const list = document.getElementById("entries");
const status = document.getElementById("status");

async function refresh() {
  const res = await fetch("/api/guestbook");
  const data = await res.json();
  list.textContent = "";
  for (const e of data.entries) {
    const li = document.createElement("li");
    li.textContent = e.name + ": " + e.message;   // textContent, never innerHTML
    list.appendChild(li);
  }
}

document.getElementById("form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const res = await fetch("/api/guestbook", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: document.getElementById("name").value,
      message: document.getElementById("message").value,
    }),
  });
  status.textContent = "Server answered " + res.status + " " + res.statusText;
  ev.target.reset();
  refresh();
});

refresh();
