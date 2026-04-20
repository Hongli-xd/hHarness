"""Simplified historian coordinator for 2-agent coordination.

The historian coordinator manages:
1. Main agent: Handles historical narration and reasoning
2. KG verifier agent: Sub-agent for verifying facts against the knowledge graph

This lightweight coordination reduces hallucination by cross-checking
critical facts before including them in the narrative.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from ..agent.tools import ToolRegistry


@dataclass
class VerificationResult:
    """Result of KG verification for a claim."""

    claim: str
    verified: bool
    sources: list[str] = field(default_factory=list)
    credibility: str = "unknown"
    conflicts: list[str] = field(default_factory=list)
    notes: str | None = None


@dataclass
class HistorianCoordinator:
    """Simplified 2-agent coordinator for historical research.

    Architecture:
    - Main agent: Primary historical reasoning and narration
    - KG verifier: Sub-agent that verifies claims against knowledge graph

    The coordinator:
    1. Receives research queries from the user
    2. Routes claims to KG verifier for fact-checking
    3. Synthesizes verified claims into coherent narrative
    """

    kg_verifier: KGVerifierAgent | None = None
    verification_threshold: float = 0.7  # Min credibility to accept claim

    async def verify_claims(self, claims: list[str]) -> list[VerificationResult]:
        """Verify a list of claims against the knowledge graph.

        Args:
            claims: List of historical claims to verify

        Returns:
            List of VerificationResults with verification status
        """
        if not self.kg_verifier:
            return [
                VerificationResult(claim=c, verified=False, notes="KG verifier not configured")
                for c in claims
            ]

        tasks = [self.kg_verifier.verify_claim(claim) for claim in claims]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        verified_results = []
        for result in results:
            if isinstance(result, Exception):
                verified_results.append(
                    VerificationResult(claim=str(result), verified=False, notes="Verification error")
                )
            else:
                verified_results.append(result)

        return verified_results

    async def filter_verified_claims(
        self, claims: list[str]
    ) -> tuple[list[str], list[str]]:
        """Filter claims into verified and unverified.

        Args:
            claims: Claims to filter

        Returns:
            Tuple of (verified_claims, unverified_claims)
        """
        results = await self.verify_claims(claims)

        verified = []
        unverified = []

        for claim, result in zip(claims, results):
            if result.verified:
                verified.append(claim)
            else:
                unverified.append(claim)

        return verified, unverified

    def synthesize_narrative(
        self,
        verified_claims: list[VerificationResult],
        unverified_claims: list[tuple[str, str]],
    ) -> str:
        """Synthesize claims into a historical narrative.

        Args:
            verified_claims: Claims that passed KG verification
            unverified_claims: Tuples of (claim, reason_unverified)

        Returns:
            Formatted historical narrative
        """
        lines = []

        # Verified claims with sources
        if verified_claims:
            lines.append("## Verified Historical Claims\n")
            for result in verified_claims:
                cred_tag = f"[{result.credibility}]"
                sources_str = ", ".join(f"[{s}]" for s in result.sources) if result.sources else ""
                lines.append(f"- {result.claim} {cred_tag} {sources_str}")
            lines.append("")

        # Unverified claims with caveats
        if unverified_claims:
            lines.append("## Claims Requiring Further Verification\n")
            for claim, reason in unverified_claims:
                lines.append(f"- {claim}")
                lines.append(f"  _Note: {reason}_")
            lines.append("")

        return "\n".join(lines)


@dataclass
class KGVerifierAgent:
    """Sub-agent for verifying historical claims against the knowledge graph.

    This agent focuses exclusively on factual verification, reducing
    the main agent's hallucination risk.
    """

    tool_registry: ToolRegistry | None = None
    rag_client: Any = None  # LightRAGClient

    async def verify_claim(self, claim: str) -> VerificationResult:
        """Verify a single claim against the knowledge graph.

        Args:
            claim: The historical claim to verify

        Returns:
            VerificationResult with verification status and sources
        """
        if not self.rag_client:
            return VerificationResult(
                claim=claim,
                verified=False,
                notes="LightRAG client not configured",
            )

        try:
            # Search for entities related to the claim
            entity_results = await self.rag_client.search_labels(claim, limit=5)

            if not entity_results:
                return VerificationResult(
                    claim=claim,
                    verified=False,
                    notes="No matching entities found in knowledge graph",
                )

            # Get detailed info for top matches
            entity_infos = []
            for entity_name in entity_results[:3]:
                try:
                    info = await self.rag_client.get_entity_info(entity_name)
                    entity_infos.append(info)
                except Exception:
                    continue

            if not entity_infos:
                return VerificationResult(
                    claim=claim,
                    verified=False,
                    notes="Could not retrieve entity details",
                )

            # Check if any entity directly supports the claim
            supporting_sources = [e.entity_name for e in entity_infos]

            return VerificationResult(
                claim=claim,
                verified=True,
                sources=supporting_sources,
                credibility=self._assess_credibility(entity_infos),
            )

        except Exception as e:
            return VerificationResult(
                claim=claim,
                verified=False,
                notes=f"Verification error: {str(e)}",
            )

    def _assess_credibility(self, entity_infos: list) -> str:
        """Assess the credibility of supporting sources.

        Args:
            entity_infos: List of EntityInfo objects

        Returns:
            Credibility level string
        """
        # Simple heuristic: check entity types
        has_primary = any(
            e.entity_type in {"史书", "档案", "金石", "考古"}
            for e in entity_infos
        )
        has_scholarly = any(
            e.entity_type in {"学术专著", "研究", "论文"}
            for e in entity_infos
        )

        if has_primary:
            return "一手文献"
        elif has_scholarly:
            return "二手研究"
        else:
            return "未知"
