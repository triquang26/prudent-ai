"""Pure ML.ENERGY JSON → domain objects — no I/O."""

from __future__ import annotations

from .models import EnergyConfig, ModelTaskFile


class MLEnergyParser:
    """Parse ML.ENERGY leaderboard JSON files into domain objects."""

    def parse_filename(self, filename: str) -> tuple[str, str] | None:
        """Extract (model_id, task) from filename.

        Filename format: {org}__{model}__{task}.json
        e.g. "Qwen__Qwen3-14B__gpqa.json"
             "meta-llama__Llama-3.3-70B-Instruct__lm-arena-chat.json"

        Returns:
            (model_id, task) where model_id uses "/" not "__",
            or None if the filename cannot be parsed.
        """
        if not filename.endswith(".json"):
            return None
        stem = filename[:-5]   # strip .json
        # Split on "__" to get [org, model, task]
        # task is the last __ segment; org/model is everything before last two segments
        parts = stem.split("__")
        if len(parts) < 3:
            return None
        task = parts[-1]
        # org is parts[0], model is everything between: parts[1:-1]
        org = parts[0]
        model_parts = parts[1:-1]
        model_name = "__".join(model_parts)
        model_id = f"{org}/{model_name}"
        return model_id, task

    def parse_model_task(self, filename: str, raw: dict) -> ModelTaskFile | None:
        """Parse one {model}__{task}.json into a ModelTaskFile."""
        parsed = self.parse_filename(filename)
        if parsed is None:
            return None
        model_id, task = parsed

        configs: list[EnergyConfig] = []
        for cfg in raw.get("configurations", []):
            ec = self._parse_config(model_id, task, cfg)
            if ec is not None:
                configs.append(ec)

        if not configs:
            return None

        return ModelTaskFile(
            filename=filename,
            model_id=model_id,
            task=task,
            configurations=configs,
        )

    @staticmethod
    def _parse_config(model_id: str, task: str, cfg: dict) -> EnergyConfig | None:
        try:
            gpu_model = cfg.get("gpu_model", "")
            max_num_seqs = int(cfg.get("max_num_seqs", 0))
            energy = float(cfg["energy_per_request_joules"])
            energy_per_token = float(cfg["energy_per_token_joules"])
            throughput = float(cfg["output_throughput_tokens_per_sec"])
            p95_itl = float(cfg["p95_itl_ms"])
            p99_itl = cfg.get("p99_itl_ms")
            num_gpus = int(cfg.get("num_gpus", 1))
            avg_power = float(cfg.get("avg_power_watts", 0.0))

            if energy <= 0 or throughput <= 0:
                return None

            return EnergyConfig(
                model_id=model_id,
                task=task,
                gpu_model=gpu_model,
                max_num_seqs=max_num_seqs,
                energy_per_request_joules=energy,
                energy_per_token_joules=energy_per_token,
                output_throughput_tokens_per_sec=throughput,
                p95_itl_ms=p95_itl,
                p99_itl_ms=float(p99_itl) if p99_itl is not None else None,
                num_gpus=num_gpus,
                avg_power_watts=avg_power,
            )
        except (KeyError, TypeError, ValueError):
            return None
