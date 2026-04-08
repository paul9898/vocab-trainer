import { useEffect, useState } from "react";
import { api } from "./api";
import { DrillPage } from "./pages/DrillPage";
import { GraphPage } from "./pages/GraphPage";
import { StatsPage } from "./pages/StatsPage";
import { StoryPage } from "./pages/StoryPage";
import type { Account, Profile } from "./types";

type Page = "drill" | "story" | "graph" | "stats";

const pages: { id: Page; label: string }[] = [
  { id: "drill", label: "Drill" },
  { id: "story", label: "Story" },
  { id: "graph", label: "Graph" },
  { id: "stats", label: "Stats" },
];

export default function App() {
  const [page, setPage] = useState<Page>("drill");
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [currentAccountId, setCurrentAccountId] = useState<string>("");
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [currentProfileId, setCurrentProfileId] = useState<string>("");
  const [profileError, setProfileError] = useState("");
  const [profileRefreshToken, setProfileRefreshToken] = useState(0);

  useEffect(() => {
    void loadAccounts();
  }, []);

  async function loadAccounts() {
    try {
      const nextAccounts = await api.getAccounts();
      setAccounts(nextAccounts);
      setProfileError("");

      const savedAccountId = window.localStorage.getItem("mastery-account-id") ?? "";
      const initialAccount =
        nextAccounts.find((account) => account.id === savedAccountId) ??
        nextAccounts[0] ??
        null;
      if (initialAccount) {
        setCurrentAccountId(initialAccount.id);
        window.localStorage.setItem("mastery-account-id", initialAccount.id);
        await loadProfiles(initialAccount.id);
      }
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Unable to load accounts.");
    }
  }

  async function loadProfiles(accountId: string) {
    try {
      const nextProfiles = await api.getProfiles(accountId);
      setProfiles(nextProfiles);
      setProfileError("");

      const savedProfileId = window.localStorage.getItem(`mastery-profile-id:${accountId}`) ?? "";
      const initialProfile =
        nextProfiles.find((profile) => profile.id === savedProfileId) ??
        nextProfiles[0] ??
        null;
      if (initialProfile) {
        setCurrentProfileId(initialProfile.id);
        window.localStorage.setItem(`mastery-profile-id:${accountId}`, initialProfile.id);
      } else {
        setCurrentProfileId("");
      }
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Unable to load profiles.");
    }
  }

  async function handleCreateAccount() {
    const name = window.prompt("Account name");
    if (!name?.trim()) return;

    try {
      const createdAccount = await api.createAccount({ name });
      const createdProfile = await api.createProfile({ account_id: createdAccount.id, name: "Main" });
      const nextAccounts = [...accounts, createdAccount].sort((a, b) => a.name.localeCompare(b.name));
      setAccounts(nextAccounts);
      setCurrentAccountId(createdAccount.id);
      setProfiles([createdProfile]);
      setCurrentProfileId(createdProfile.id);
      window.localStorage.setItem("mastery-account-id", createdAccount.id);
      window.localStorage.setItem(`mastery-profile-id:${createdAccount.id}`, createdProfile.id);
      setProfileError("");
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Unable to create account.");
    }
  }

  async function handleCreateProfile() {
    if (!currentAccountId) return;
    const name = window.prompt("Profile name");
    if (!name?.trim()) return;

    try {
      const created = await api.createProfile({ account_id: currentAccountId, name });
      const nextProfiles = [...profiles, created].sort((a, b) => a.name.localeCompare(b.name));
      setProfiles(nextProfiles);
      setCurrentProfileId(created.id);
      window.localStorage.setItem(`mastery-profile-id:${currentAccountId}`, created.id);
      setProfileError("");
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Unable to create profile.");
    }
  }

  async function handleResetProfile() {
    const activeProfile = profiles.find((profile) => profile.id === currentProfileId);
    if (!activeProfile) return;
    const confirmed = window.confirm(`Reset all progress for '${activeProfile.name}'?`);
    if (!confirmed) return;

    try {
      await api.resetProfile(activeProfile.id);
      setProfileError("");
      setPage("drill");
      setProfileRefreshToken((current) => current + 1);
    } catch (error) {
      setProfileError(error instanceof Error ? error.message : "Unable to reset profile.");
    }
  }

  function handleProfileChange(profileId: string) {
    setCurrentProfileId(profileId);
    if (currentAccountId) {
      window.localStorage.setItem(`mastery-profile-id:${currentAccountId}`, profileId);
    }
  }

  async function handleAccountChange(accountId: string) {
    setCurrentAccountId(accountId);
    window.localStorage.setItem("mastery-account-id", accountId);
    setCurrentProfileId("");
    await loadProfiles(accountId);
  }

  return (
    <div className="min-h-screen text-ink">
      <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 py-6 md:px-6 md:py-8">
        <header className="glass-panel rounded-[30px] px-5 py-4 shadow-soft md:px-6">
          <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-ink/45">Mastery app</p>
              <h1 className="font-display text-3xl text-ink">Thai Vocab Mastery</h1>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-4 py-2 text-sm text-ink">
                <span className="font-semibold">Account</span>
                <select
                  value={currentAccountId}
                  onChange={(event) => void handleAccountChange(event.target.value)}
                  className="bg-transparent outline-none"
                >
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="flex items-center gap-2 rounded-full border border-black/10 bg-white/70 px-4 py-2 text-sm text-ink">
                <span className="font-semibold">Profile</span>
                <select
                  value={currentProfileId}
                  onChange={(event) => handleProfileChange(event.target.value)}
                  disabled={!currentAccountId || profiles.length === 0}
                  className="bg-transparent outline-none"
                >
                  {profiles.map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                onClick={() => void handleCreateAccount()}
                className="rounded-full border border-black/10 bg-white/70 px-4 py-2 text-sm font-semibold text-ink hover:bg-white"
              >
                New account
              </button>
              <button
                type="button"
                onClick={() => void handleCreateProfile()}
                disabled={!currentAccountId}
                className="rounded-full border border-black/10 bg-white/70 px-4 py-2 text-sm font-semibold text-ink hover:bg-white"
              >
                New profile
              </button>
              <button
                type="button"
                onClick={() => void handleResetProfile()}
                disabled={!currentProfileId}
                className="rounded-full border border-black/10 bg-white/70 px-4 py-2 text-sm font-semibold text-ink hover:bg-white disabled:opacity-50"
              >
                Reset progress
              </button>
              <nav className="flex flex-wrap gap-2">
                {pages.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setPage(item.id)}
                    className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                      page === item.id
                        ? "bg-ink text-white"
                        : "border border-black/10 bg-white/70 text-ink hover:bg-white"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </nav>
            </div>
          </div>
          {profileError ? <p className="mt-3 text-sm text-clay">{profileError}</p> : null}
        </header>

        <main className="flex-1 py-6 md:py-8">
          {page === "drill" && currentProfileId ? <DrillPage key={`${currentProfileId}:${profileRefreshToken}`} profileId={currentProfileId} /> : null}
          {page === "story" && currentProfileId ? <StoryPage key={`${currentProfileId}:${profileRefreshToken}`} profileId={currentProfileId} /> : null}
          {page === "graph" && currentProfileId ? <GraphPage key={`${currentProfileId}:${profileRefreshToken}`} profileId={currentProfileId} /> : null}
          {page === "stats" && currentProfileId ? <StatsPage key={`${currentProfileId}:${profileRefreshToken}`} profileId={currentProfileId} /> : null}
        </main>
      </div>
    </div>
  );
}
