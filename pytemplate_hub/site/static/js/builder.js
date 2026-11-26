// A pack page's command builder: a project name, a profile, and three commands (create, preview,
// and the fully pinned form for CI). It sets text and data attributes only; it never builds HTML.
// The address keeps the choice (?profile=…&name=…), which "Copy link" copies.

const $ = (id) => document.getElementById(id);
const builder = document.querySelector("[data-builder]");
const NAME = /^[a-z][a-z0-9-]*[a-z0-9]$|^[a-z]$/;

if (builder) {
  const { pack, tag, source, commit, digest } = builder.dataset;
  const tabs = [...builder.querySelectorAll("[data-tab]")];
  const picks = [...document.querySelectorAll("[data-profile-pick]")];
  const details = [...document.querySelectorAll("[data-profile-detail]")];
  const profiles = [...$("b-profile").options].map((option) => option.value);
  const tabNames = tabs.map((tab) => tab.dataset.tab);
  const state = { tab: "create", name: "my-project", profile: profiles[0], yes: true };
  let dirty = Boolean(location.search);

  const params = new URLSearchParams(location.search);
  if (profiles.includes(params.get("profile"))) state.profile = params.get("profile");
  if (NAME.test(params.get("name") || "")) state.name = params.get("name");
  if (tabNames.includes(params.get("tab"))) state.tab = params.get("tab");
  if (params.get("yes") === "0") state.yes = false;

  function command() {
    if (state.tab === "plan") return `uvx pytemplate-uv@latest plan --name ${state.name} -h ${pack}@${tag} -p ${state.profile}`;
    if (state.tab === "pinned") {
      return `uvx pytemplate-uv@latest create ${state.name} -p ${state.profile} --template ${source} `
        + `--template-ref ${tag} --template-commit ${commit} --template-digest ${digest} -y`;
    }
    return `uvx pytemplate-uv@latest create ${state.name} -h ${pack}@${tag} -p ${state.profile}${state.yes ? " -y" : ""}`;
  }

  function multiline(cmd) {
    return cmd.replace(/ (--template |--template-commit |--template-digest )/g, " \\\n  $1");
  }

  const NOTES = {
    create: `pytemplate-uv 3.5 or later reads the commit and digest the hub checked for ${tag}, refuses the pack if anything changed, and writes nothing.`,
    plan: "plan lists the files and the dependencies the project would get. It writes nothing.",
    pinned: "The commit and digest are in the command itself, so it never reads the hub's index: for CI and machines without network access.",
  };

  function update() {
    const valid = NAME.test(state.name);
    const help = $("b-name-help");
    $("b-name").setAttribute("aria-invalid", String(!valid));
    help.className = valid ? "" : "err";
    help.textContent = valid ? "A lowercase name, for example market-data-api." : "Use lowercase letters, digits, and hyphens, starting with a letter.";
    const text = command();
    $("b-cmd").textContent = multiline(text);
    $("b-copy").dataset.copy = text;
    $("b-copy").disabled = !valid;
    $("b-note").textContent = NOTES[state.tab];
    $("b-yes-row").hidden = state.tab !== "create";
    $("b-yes").checked = state.yes;
    for (const tab of tabs) tab.setAttribute("aria-selected", String(tab.dataset.tab === state.tab));
    for (const pick of picks) pick.checked = pick.value === state.profile;
    for (const detail of details) detail.hidden = detail.dataset.profileDetail !== state.profile;
    $("b-profile").value = state.profile;
    const query = new URLSearchParams({ profile: state.profile, name: state.name });
    if (state.tab !== "create") query.set("tab", state.tab);
    if (!state.yes) query.set("yes", "0");
    const shareUrl = `${location.href.split("?")[0].split("#")[0]}?${query}`;
    if (dirty) history.replaceState(null, "", `?${query}`);
    $("b-link").dataset.copy = shareUrl;
  }

  $("b-name").value = state.name;
  $("b-name").addEventListener("input", (event) => { dirty = true; state.name = event.target.value.trim(); update(); });
  $("b-profile").addEventListener("change", (event) => { dirty = true; state.profile = event.target.value; update(); });
  $("b-yes").addEventListener("change", (event) => { dirty = true; state.yes = event.target.checked; update(); });
  for (const tab of tabs) tab.addEventListener("click", () => { dirty = true; state.tab = tab.dataset.tab; update(); });
  for (const pick of picks) pick.addEventListener("change", () => { dirty = true; state.profile = pick.value; update(); });
  update();
}
