import { useState } from "react";
import { createRoot } from "react-dom/client";
import { PaymentPlanEditor, newPaymentPlan } from "../src/components/PaymentPlanEditor";
import { ThemeProvider } from "../src/theme/ThemeContext";
function Fixture() {
  const [plan, setPlan] = useState(newPaymentPlan);
  const [valid, setValid] = useState(false);
  return <ThemeProvider><form onSubmit={(e) => { e.preventDefault(); document.body.dataset.saved = JSON.stringify(plan); }}><PaymentPlanEditor total="1000" anchorDate="2026-09-22" value={plan} onChange={setPlan} onValid={setValid} /><button disabled={!valid}>Save synthetic plan</button></form></ThemeProvider>;
}
createRoot(document.getElementById("root")!).render(<Fixture />);
