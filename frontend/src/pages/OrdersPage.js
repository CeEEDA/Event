import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Logo } from "../components/Logo";
import { Button } from "../components/ui/button";
import {
  ArrowLeft,
  Plus,
  ClipboardList,
  Search,
} from "lucide-react";

export default function OrdersPage() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col" data-testid="orders-page">
      <header className="bg-white border-b border-gray-200 p-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="sm" onClick={() => navigate("/hub")} className="text-gray-600 hover:text-fuchsia-600" data-testid="back-to-hub-btn">
              <ArrowLeft className="w-4 h-4 mr-2" /> Zurück
            </Button>
            <div className="h-6 w-px bg-gray-200" />
            <h1 className="text-lg font-semibold text-gray-900">Auftragsverwaltung</h1>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Auftrag suchen..."
                className="pl-9 pr-4 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:border-fuchsia-500 w-64"
                data-testid="order-search-input"
              />
            </div>
            <Button size="sm" className="bg-fuchsia-600 hover:bg-fuchsia-700 text-white" data-testid="new-order-btn">
              <Plus className="w-4 h-4 mr-1" /> Neuer Auftrag
            </Button>
            <Logo size="small" />
          </div>
        </div>
      </header>

      <main className="flex-1 flex items-center justify-center p-4 md:p-8">
        <div className="text-center">
          <ClipboardList className="w-16 h-16 text-gray-300 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-gray-900 mb-2">Auftragsverwaltung</h2>
          <p className="text-sm text-gray-500 max-w-md">
            Hier werden Aufträge angezeigt und verwaltet. Die Verknüpfung mit EpiRent folgt im nächsten Schritt.
          </p>
        </div>
      </main>
    </div>
  );
}
