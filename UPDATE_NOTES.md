# Update v3.3 (drag these onto your GitHub repo, same folders)

Changed: run.py (new SAMPLE_MODE=true fallback), app/synthetic.py (realistic many-stock-out generator, supplier fill-rate setting), scripts/generate_data.py (new --many, --fill, --noise options), app/tools/nvidia_client.py (real client replacing the placeholder).
New: scripts/score_events.py, scripts/import_real_facilities.py, scripts/extract_budget.py, scripts/nvidia_smoke_test.py, scripts/test_nvidia_client.py.

Also add these lines to .env.example (GitHub's upload skips dot-files, so paste them by hand):

# NVIDIA model name: copy it exactly from the model page on build.nvidia.com
NVIDIA_MODEL=
# Optional: only change if the organisers or Meterless give you a different gateway address
# NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
# Set to true to run on the local data only, without Zetaris or any outside service
SAMPLE_MODE=false

Existing example inputs and outputs are unchanged.
