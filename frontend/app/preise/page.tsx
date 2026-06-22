import { api, type ModelPrice } from "@/lib/api";
import { getT } from "@/lib/i18n/server";

export const dynamic = "force-dynamic";

export default async function PreisePage() {
  const t = getT();
  let prices: ModelPrice[] = [];
  try {
    prices = await api.pricing.list();
  } catch {}
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="mb-4 text-2xl font-bold">{t("preise.title")}</h1>
      <p className="mb-4 text-sm text-muted-foreground">{t("preise.intro")}</p>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left">
            <th className="py-2">{t("preise.provider")}</th>
            <th>{t("preise.model")}</th>
            <th className="text-right">{t("preise.input")}</th>
            <th className="text-right">{t("preise.output")}</th>
          </tr>
        </thead>
        <tbody>
          {prices.map((p) => (
            <tr key={p.model} className="border-b">
              <td className="py-2">{p.provider}</td>
              <td>{p.label}</td>
              <td className="text-right">
                ${Number(p.portal_input_per_million_usd).toFixed(2)}
              </td>
              <td className="text-right">
                ${Number(p.portal_output_per_million_usd).toFixed(2)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
