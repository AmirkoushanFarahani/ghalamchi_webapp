import { useState } from "react";
import { createRoot } from "react-dom/client";
import { Modal } from "../src/components/ui";

function Fixture() {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  return <>
    <button id="opener" onClick={() => setOpen(true)}>Open</button>
    <Modal open={open} title="Focus regression" onClose={() => { if (!busy) setOpen(false); }}>
      <label>Reason<textarea id="reason" value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500}/></label>
      <button id="busy" onClick={() => setBusy(!busy)}>{busy ? "Unlock" : "Lock"}</button>
    </Modal>
  </>;
}

createRoot(document.getElementById("root")!).render(<Fixture/>);
