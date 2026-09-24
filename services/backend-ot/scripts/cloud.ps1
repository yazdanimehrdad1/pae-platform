# GKE / Cloud SQL cost control for Windows. Called by `make cloud-down` / `make cloud-up`
# (the Makefile's non-Windows branch has the same logic in POSIX sh). On Windows, kubectl
# needs gke-gcloud-auth-plugin, which is on the PowerShell PATH but usually not on make's.
# Moved verbatim from the former make.ps1 — deployment tooling, intentionally unchanged.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File scripts/cloud.ps1 <cloud-down|cloud-up>

param(
    [Parameter(Position=0, Mandatory=$true)]
    [ValidateSet("cloud-down", "cloud-up")]
    [string]$Command
)

switch ($Command) {
    "cloud-down" {
        # Stop all billable GCP compute (app + redis + ArgoCD -> 0, Cloud SQL stopped).
        # Data is preserved; idle cost ~= Cloud SQL storage only.
        $proj = "prd-pae-backend-ot"; $sql = "pae-backend-ot-pg-prod"; $ns = "pae-backend-ot-prod"
        # Ensure kubectl + gke-gcloud-auth-plugin are on PATH (robust when invoked via `make`).
        $env:Path += ";$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin"
        Write-Host ">> Stopping ArgoCD (so it won't scale things back up)..." -ForegroundColor Yellow
        kubectl -n argocd scale statefulset --all --replicas=0
        kubectl -n argocd scale deploy --all --replicas=0
        Write-Host ">> Removing HPA (it would otherwise force min replicas)..." -ForegroundColor Yellow
        kubectl -n $ns delete hpa pae-backend-ot --ignore-not-found
        Write-Host ">> Scaling app + redis to 0..." -ForegroundColor Yellow
        kubectl -n $ns scale deploy pae-backend-ot redis --replicas=0
        Write-Host ">> Stopping Cloud SQL..." -ForegroundColor Yellow
        gcloud sql instances patch $sql --project=$proj --activation-policy=NEVER --quiet
        Write-Host ">> cloud-down complete. Billing minimized (data preserved)." -ForegroundColor Green
    }
    "cloud-up" {
        # Start Cloud SQL, bring ArgoCD back, scale workloads up, let ArgoCD reconcile.
        $proj = "prd-pae-backend-ot"; $sql = "pae-backend-ot-pg-prod"; $ns = "pae-backend-ot-prod"
        # Ensure kubectl + gke-gcloud-auth-plugin are on PATH (robust when invoked via `make`).
        $env:Path += ";$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin"
        Write-Host ">> Starting Cloud SQL..." -ForegroundColor Green
        gcloud sql instances patch $sql --project=$proj --activation-policy=ALWAYS --quiet
        Write-Host ">> Waiting for Cloud SQL to be RUNNABLE..." -ForegroundColor Cyan
        do {
            Start-Sleep -Seconds 10
            $state = gcloud sql instances describe $sql --project=$proj --format="value(state)"
            Write-Host "   ...state=$state"
        } while ($state -ne "RUNNABLE")
        Write-Host ">> Bringing ArgoCD back..." -ForegroundColor Green
        kubectl -n argocd scale statefulset --all --replicas=1
        kubectl -n argocd scale deploy --all --replicas=1
        kubectl -n argocd rollout status statefulset/argocd-application-controller --timeout=180s
        kubectl -n argocd rollout status deploy/argocd-repo-server --timeout=120s
        Write-Host ">> Scaling redis + app back up..." -ForegroundColor Green
        kubectl -n $ns scale deploy redis --replicas=1
        kubectl -n $ns rollout status deploy/redis --timeout=120s
        kubectl -n $ns scale deploy pae-backend-ot --replicas=2
        kubectl -n $ns rollout status deploy/pae-backend-ot --timeout=240s
        Write-Host ">> Nudging ArgoCD to reconcile (recreates HPA, marks Synced)..." -ForegroundColor Green
        kubectl -n argocd annotate application pae-backend-ot-prod argocd.argoproj.io/refresh=hard --overwrite | Out-Null
        Write-Host ">> cloud-up complete. App is ready." -ForegroundColor Green
    }
}
