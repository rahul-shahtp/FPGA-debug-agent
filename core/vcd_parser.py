"""
VCD (Value Change Dump) Parser Module.

Parses standard IEEE 1364-2001 VCD files, extracting signal definitions
and value change data with efficient memory handling for large files.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class SignalDefinition:
    """Represents a signal definition from the VCD header."""
    identifier: str
    name: str
    width: int
    scope: str
    var_type: str


@dataclass
class ValueChange:
    """Represents a single value change event."""
    timestamp: int
    identifier: str
    value: str


@dataclass
class VCDData:
    """Container for parsed VCD data."""
    timescale: str = ""
    date: str = ""
    version: str = ""
    signals: Dict[str, SignalDefinition] = field(default_factory=dict)
    transitions: Dict[str, List[Tuple[int, str]]] = field(default_factory=dict)
    end_time: int = 0

    def get_signal_by_name(self, name: str) -> Optional[SignalDefinition]:
        """Look up a signal definition by its full hierarchical name."""
        for sig in self.signals.values():
            full_name = f"{sig.scope}.{sig.name}" if sig.scope else sig.name
            if full_name == name or sig.name == name:
                return sig
        return None

    def get_transitions(self, identifier: str) -> List[Tuple[int, str]]:
        """Get all transitions for a signal identifier."""
        return self.transitions.get(identifier, [])

    def get_signal_names(self) -> List[str]:
        """Get list of all signal names with full scope."""
        names = []
        for sig in self.signals.values():
            full_name = f"{sig.scope}.{sig.name}" if sig.scope else sig.name
            names.append(full_name)
        return names


class VCDParser:
    """
    Parser for IEEE 1364-2001 VCD files.

    Handles standard VCD keywords: $date, $version, $timescale,
    $scope, $upscope, $var, $enddefinitions, $dumpvars, $end.

    Supports scalar and vector signals with efficient streaming parsing.
    """

    # Regex patterns for VCD parsing
    _TIMESTAMP_RE = re.compile(r'^#(\d+)')
    _SCALAR_RE = re.compile(r'^([01xXzZ])(.+)')
    _VECTOR_RE = re.compile(r'^[bBrR]([01xXzZ]+)\s+(.+)')

    def __init__(self) -> None:
        self._data = VCDData()
        self._scope_stack: List[str] = []
        self._current_time: int = 0

    def parse(self, filepath: str) -> VCDData:
        """
        Parse a VCD file and return structured data.

        Args:
            filepath: Path to the VCD file.

        Returns:
            VCDData object containing signals and transitions.

        Raises:
            FileNotFoundError: If the VCD file does not exist.
            ValueError: If the VCD file is malformed.
        """
        self._data = VCDData()
        self._scope_stack = []
        self._current_time = 0

        logger.info("Parsing VCD file: %s", filepath)

        try:
            with open(filepath, 'r') as f:
                self._parse_stream(f)
        except FileNotFoundError:
            logger.error("VCD file not found: %s", filepath)
            raise
        except Exception as e:
            logger.error("Error parsing VCD file: %s", e)
            raise

        logger.info(
            "Parsed %d signals with %d total transitions",
            len(self._data.signals),
            sum(len(t) for t in self._data.transitions.values())
        )
        return self._data

    def _parse_stream(self, stream) -> None:
        """Parse a VCD file stream line by line."""
        in_header = True
        token_buffer: List[str] = []
        in_keyword = False

        for line in stream:
            line = line.strip()
            if not line:
                continue

            if in_header:
                if '$enddefinitions' in line:
                    in_header = False
                    in_keyword = False
                    token_buffer = []
                    continue

                if line.startswith('$') and not in_keyword:
                    keyword = line.split()[0]
                    rest = line[len(keyword):].strip()
                    if '$end' in rest:
                        content = rest.replace('$end', '').strip()
                        self._process_header_keyword(keyword, content)
                    else:
                        in_keyword = True
                        token_buffer = [keyword, rest] if rest else [keyword]
                elif in_keyword:
                    if '$end' in line:
                        content = line.replace('$end', '').strip()
                        if content:
                            token_buffer.append(content)
                        self._process_header_keyword(
                            token_buffer[0],
                            ' '.join(token_buffer[1:])
                        )
                        in_keyword = False
                        token_buffer = []
                    else:
                        token_buffer.append(line)
                continue

            # Data section
            if line.startswith('$'):
                # Skip $dumpvars, $dumpoff, $dumpon, $dumpall, $end
                continue

            self._parse_data_line(line)

        self._data.end_time = self._current_time

    def _process_header_keyword(self, keyword: str, content: str) -> None:
        """Process a VCD header keyword."""
        if keyword == '$date':
            self._data.date = content
        elif keyword == '$version':
            self._data.version = content
        elif keyword == '$timescale':
            self._data.timescale = content
        elif keyword == '$scope':
            parts = content.split()
            if len(parts) >= 2:
                self._scope_stack.append(parts[1])
        elif keyword == '$upscope':
            if self._scope_stack:
                self._scope_stack.pop()
        elif keyword == '$var':
            self._parse_var(content)

    def _parse_var(self, content: str) -> None:
        """Parse a $var declaration."""
        parts = content.split()
        if len(parts) < 4:
            logger.warning("Malformed $var: %s", content)
            return

        var_type = parts[0]
        try:
            width = int(parts[1])
        except ValueError:
            logger.warning("Invalid width in $var: %s", content)
            return
        identifier = parts[2]
        name = parts[3]

        scope = '.'.join(self._scope_stack)
        sig = SignalDefinition(
            identifier=identifier,
            name=name,
            width=width,
            scope=scope,
            var_type=var_type
        )
        self._data.signals[identifier] = sig
        self._data.transitions[identifier] = []
        logger.debug("Registered signal: %s.%s [%s]", scope, name, identifier)

    def _parse_data_line(self, line: str) -> None:
        """Parse a single line in the data section."""
        # Timestamp
        ts_match = self._TIMESTAMP_RE.match(line)
        if ts_match:
            self._current_time = int(ts_match.group(1))
            return

        # Vector value change
        vec_match = self._VECTOR_RE.match(line)
        if vec_match:
            value = vec_match.group(1)
            identifier = vec_match.group(2).strip()
            self._record_transition(identifier, value)
            return

        # Scalar value change
        scalar_match = self._SCALAR_RE.match(line)
        if scalar_match:
            value = scalar_match.group(1)
            identifier = scalar_match.group(2).strip()
            self._record_transition(identifier, value)
            return

    def _record_transition(self, identifier: str, value: str) -> None:
        """Record a value change for a signal."""
        if identifier in self._data.transitions:
            self._data.transitions[identifier].append(
                (self._current_time, value)
            )
        else:
            logger.debug(
                "Transition for unknown signal %s at time %d",
                identifier, self._current_time
            )
