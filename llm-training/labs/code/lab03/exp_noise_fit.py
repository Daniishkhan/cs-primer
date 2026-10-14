"""Where the extra forgetting of full fine-tuning lives: in the part of the change that is not low rank."""
from solution import *

w = World()
full = run_full(w)
Wf, _ = train_full(w.W0, w.train_b, 0.005, 200)
A, B, _ = train_lora(w.W0, w.train_b, 2, 16.0, 0.02, 200)
dl = adapter_delta(A, B, 16.0)
df = mat_add(Wf, w.W0, -1.0)
true_low = w.low
print(f"squared size ||change||_F^2 of the update each method made, and how far it is from the true low-rank change:")
print(f"  true low-rank change   {frobenius_sq(true_low):6.3f}")
print(f"  true faint dense part  {frobenius_sq(w.faint):6.3f}")
print(f"  LoRA r=2 update        {frobenius_sq(dl):6.3f}   distance to true low-rank {frobenius_sq(mat_add(dl, true_low, -1.0)):6.3f}")
print(f"  full update            {frobenius_sq(df):6.3f}   distance to true low-rank {frobenius_sq(mat_add(df, true_low, -1.0)):6.3f}")
print(f"  (task-A loss = ||update||_F^2 / {D} for isotropic inputs: {frobenius_sq(dl) / D:.3f} and {frobenius_sq(df) / D:.3f})")
