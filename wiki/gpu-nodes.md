# GPU Worker Nodes on AWS (MachineSets + MIG)

How to add GPU worker nodes to the OpenShift cluster on AWS, and what to check
before you pick an instance type. Written after a session that attempted 2× H100
nodes on an RHPDS sandbox and hit a hard capacity wall — see **Status** at the end.

Related pitfalls: [#25](pitfalls.md) (selector labels), [#26](pitfalls.md) (stripping
exported YAML), [#27](pitfalls.md) (capacity errors), [#28](pitfalls.md) (MIG hardware),
[#29](pitfalls.md) (template edits don't reach existing Machines).

---

## 1. Choose the instance type *from the workload requirement*, not from price

The single most consequential decision, because it is not reversible by config.

**If you need MIG / GPU-as-a-Service partitioning**, you need a data-center GPU:
A100, A30, H100, H200, or B200. On AWS that means the **P-family only**. Every
G-family instance (`g4dn` T4, `g5` A10G, `g6` L4, `g6e` L40S) has **no MIG support
whatsoever** — see pitfall #28. Do not "fall back" to a G instance to save money;
you silently lose the entire feature.

| Instance | GPU | VRAM | MIG slices | ~$/hr | FP8 |
|---|---|---|---|---|---|
| `g4dn.2xlarge` | 1× T4 | 16 GB | — | 0.75 | No |
| `g5.2xlarge` | 1× A10G | 24 GB | — | 1.2 | No |
| `g6.2xlarge` | 1× L4 | 24 GB | — | 1.0 | Yes |
| `g6e.2xlarge` | 1× L40S | 48 GB | — | 2.2 | Yes |
| `p5.4xlarge` | 1× H100 | 80 GB | **7** | 6.88 | Yes |
| `p4d.24xlarge` | 8× A100 | 8× 40 GB | **56** | 21.96 | No |
| `p5.48xlarge` | 8× H100 | 8× 80 GB | **56** | ~98 | Yes |

`p5.4xlarge` is the cheapest MIG-capable instance AWS sells. `p4d.24xlarge` is the
standard fallback: a generation older, so capacity is far easier to obtain.

Two non-obvious constraints:

- **FP8 needs Ada or Hopper.** `redhataiqwen3-8b-fp8-dynamic` will not run natively
  on A10G or A100 (both Ampere). L4, L40S, and H100 are fine.
- **`p5.4xlarge` has no GPUDirect RDMA / EFA** — it is the one P5 size without it.
  Irrelevant for independent single-GPU inference nodes; rules out multi-node
  distributed training across a pair of them.

## 2. Derive the MachineSet from an existing worker

Never hand-write one — the AMI ID, subnet names, IAM profile and cluster tags are
all cluster-specific.

```bash
INFRA=$(oc get infrastructure cluster -o jsonpath='{.status.infrastructureName}')
oc get machineset -n openshift-machine-api "${INFRA}-worker-us-east-2b" -o yaml > gpu-machineset.yaml
```

Then apply **all five** edits:

| # | Field | Change |
|---|---|---|
| 1 | `status`, `managedFields`, `resourceVersion`, `uid`, `creationTimestamp`, `generation`, `machine.openshift.io/{GPU,vCPU,memoryMb}` annotations | **delete** (pitfall #26) |
| 2 | `metadata.name` **and both `cluster-api-machineset` labels** | `<infra>-worker-<az>` → `<infra>-gpu-<az>` (pitfall #25) |
| 3 | `…providerSpec.value.blockDevices[0].ebs.volumeSize` | `500` (GiB — model weights are large) |
| 4 | `…providerSpec.value.instanceType` | your chosen type |
| 5 | `spec.replicas` | node count |

Optional but recommended in `spec.template.spec`:

```yaml
      metadata:
        labels:
          node-role.kubernetes.io/gpu: ''
      # taint so only GPU workloads land on expensive nodes;
      # NFD and the NVIDIA GPU Operator tolerate this by default
      taints:
        - key: nvidia.com/gpu
          value: 'true'
          effect: NoSchedule
```

**Pre-apply gate** — the identity check that prevents adopting existing workers:

```bash
oc apply --dry-run=client -f gpu-machineset.yaml >/dev/null && \
python3 - <<'PY'
import re; t=open('gpu-machineset.yaml').read()
n=re.search(r'^  name: (\S+)', t, re.M).group(1)
assert t.count(f'cluster-api-machineset: {n}')==2, 'selector/template labels do NOT match metadata.name'
assert not re.search(r'(?m)^status:|managedFields|resourceVersion', t), 'server-owned fields still present'
print('OK:', n)
PY
```

## 3. Apply and verify

```bash
oc apply -f gpu-machineset.yaml
oc get machines -n openshift-machine-api -o wide | grep gpu
```

A Machine that has **no `PROVIDERID` after ~2 minutes is not provisioning** — it is
failing in a retry loop. The phase stays `Provisioning` forever and never becomes
`Failed`, so always read the events:

```bash
oc get events -n openshift-machine-api --field-selector reason=FailedCreate \
  -o jsonpath='{range .items[*]}{.lastTimestamp}{" | "}{.message}{"\n"}{end}' | tail -3
```

| Error | Meaning | Action |
|---|---|---|
| `InsufficientInstanceCapacity` | AWS has no hardware | Capacity Reservation / Capacity Blocks for ML, or a different family. **Ignore the "try AZ x, y" hint — it is just the complement of the zone you asked for** (pitfall #27) |
| `VcpuLimitExceeded` | Account quota | Raise via AWS support |
| `Unsupported` | Type not offered in that AZ | Move AZ — this one *is* a real signal |

Nothing is billed while launches fail, so a stuck MachineSet is harmless to leave
retrying; it will grab capacity the moment it frees.

**Changing the type or AZ of a stuck MachineSet requires deleting its Machines.**
A MachineSet has no rollout controller — `spec.template` only stamps *new* Machines,
and existing ones keep retrying with their original frozen `providerSpec` forever.
Patching alone silently tests nothing (pitfall #29):

```bash
oc patch machineset <name> -n openshift-machine-api --type=merge -p '{...}'
oc delete machine -n openshift-machine-api \
  -l machine.openshift.io/cluster-api-machineset=<name>   # safe: no EC2 instance exists
```

## 4. Enabling MIG once nodes join

MIG is configured by the NVIDIA GPU Operator, not the MachineSet. After the node
is `Ready` and NFD has labelled it:

```bash
# single = all slices identical; mixed = heterogeneous profiles per GPU
oc label node <gpu-node> nvidia.com/mig.config=all-1g.10gb --overwrite
oc get node <gpu-node> -o jsonpath='{.metadata.labels.nvidia\.com/mig\.config\.state}'
```

H100 80GB profiles: `1g.10gb` (×7), `1g.20gb`, `2g.20gb`, `3g.40gb`, `4g.40gb`, `7g.80gb`.
A100 40GB profiles: `1g.5gb` (×7), `2g.10gb`, `3g.20gb`, `7g.40gb`.

Verify slices are advertised: `oc describe node <gpu-node> | grep nvidia.com/`

---

## Status of the 2026-09-09 attempt

**Not provisioned.** Target was 2× `p5.4xlarge` (1× H100 80GB each, 7 MIG slices
per node) on cluster `cluster-sznd8-xwp4m` in `us-east-2`.

The MachineSet is correct and applied — `cluster-sznd8-xwp4m-gpu-us-east-2b`,
`DESIRED 2 / READY 0`, retrying indefinitely at no cost. AWS returns
`InsufficientInstanceCapacity` for `p5.4xlarge` in **both** AZs the cluster has
private subnets in (`us-east-2b`, `us-east-2c`); the cluster has no subnet in
`us-east-2a`.

Every failure was capacity — **zero `VcpuLimitExceeded` events**, so this is not a
quota wall that a support ticket could raise. P5 capacity generally requires
Capacity Blocks for ML, which RHPDS sandbox accounts do not get.

Unverified: direct confirmation against the AWS API (`describe-instance-type-offerings`,
service quotas) was not possible — reading the `aws-cloud-credentials` secret was
blocked. The conclusion rests on ~15 minutes of EC2 error responses, not an API query.

**Re-checked 2026-09-10 (+17h):** still zero instances. The MachineSet retried
continuously overnight — machine-controller logs confirm live `creating machine`
attempts — and both AZs were re-tested from a clean set of Machines. Same
`InsufficientInstanceCapacity` in `us-east-2b` and `us-east-2c`. A 17-hour window with
no capacity in either zone points at the account lacking on-demand P5 access rather
than transient scarcity.

**Open options:** leave it retrying; switch to `p4d.24xlarge` (A100, MIG-capable,
much better availability, ~$22/hr/node); or confirm the sandbox was ordered with GPU
entitlement at all — RHPDS clusters normally get GPU nodes from a GPU-specific
catalog item at order time. Given the overnight result, **the entitlement check is now
the first thing to do** — it is free and would explain everything.
