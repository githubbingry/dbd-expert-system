import base64
import hmac
import json
import time
from functools import wraps
from hashlib import sha256
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
import bcrypt
from flask import Flask, render_template, request, jsonify, redirect, make_response
from config_store import (
    ALL_VARIABLES,
    DERIVED_VALUES,
    INPUT_VARIABLES,
    load_cf_config,
    load_questions,
    load_rules_data,
    normalize_cf,
    save_cf_config,
    save_questions,
    save_rules_data,
    validate_questions,
    validate_rule,
)

app = Flask(__name__)
app.secret_key = 'dbd-expert-system-secret-key'
JWT_SECRET = app.secret_key.encode("utf-8")
AUTH_COOKIE = "dbd_admin_token"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD_HASH = b"$2a$12$CQMgCnpIVjgxyJR5vu3li.7knYlB1DSd5RjzSDkXODo.Ctex1JZC6"
TOKEN_MAX_AGE_SECONDS = 8 * 60 * 60

RULES_DATA = load_rules_data()
QUESTIONS = load_questions()
CF_CONFIG = load_cf_config()


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def create_jwt(username: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": username,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_MAX_AGE_SECONDS,
    }
    header_part = b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_part = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    signature = hmac.new(JWT_SECRET, signing_input, sha256).digest()
    return f"{header_part}.{payload_part}.{b64url_encode(signature)}"


def verify_jwt(token: str) -> Optional[Dict[str, Any]]:
    try:
        header_part, payload_part, signature_part = token.split(".")
        signing_input = f"{header_part}.{payload_part}".encode("ascii")
        expected = hmac.new(JWT_SECRET, signing_input, sha256).digest()
        supplied = b64url_decode(signature_part)
        if not hmac.compare_digest(expected, supplied):
            return None
        payload = json.loads(b64url_decode(payload_part))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        if payload.get("sub") != ADMIN_USERNAME:
            return None
        return payload
    except Exception:
        return None


def current_admin() -> Optional[Dict[str, Any]]:
    token = request.cookies.get(AUTH_COOKIE)
    if not token:
        return None
    return verify_jwt(token)


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if current_admin():
            return view_func(*args, **kwargs)
        if request.path.startswith("/api/"):
            return jsonify({"error": "Unauthorized"}), 401
        return redirect("/login")
    return wrapper


def refresh_runtime_data():
    global RULES_DATA, QUESTIONS, CF_CONFIG, knowledge_base, engine
    RULES_DATA = load_rules_data()
    QUESTIONS = load_questions()
    CF_CONFIG = load_cf_config()
    knowledge_base = KnowledgeBase(RULES_DATA)
    engine = BackwardChainingEngine(knowledge_base)


@dataclass
class Fact:
    attribute: str
    value: str
    derived: bool = False
    rule_used: Optional[int] = None


@dataclass
class Rule:
    rule_id: int
    set: int
    antecedents: List[Dict[str, Any]]
    consequent: Dict[str, str]
    description: str = ""
    cf: float = 1.0


@dataclass
class DebugStep:
    """Trace step for debugging"""
    type: str  # 'goal_start', 'goal_found', 'rule_try', 'rule_fire', 'rule_fail', 'ask', 'fact_known', 'backtrack'
    depth: int
    message: str
    rule_id: int = None
    attribute: str = None
    value: str = None
    timestamp: int = field(default_factory=lambda: 0)


class KnowledgeBase:
    def __init__(self, rules_data: dict):
        self.rules = self._load_rules(rules_data)
        self.goal_variables = ['tingkat_resiko_dbd']
        self.all_variables = ALL_VARIABLES
        
        # Group rules by set for easier lookup
        self.rules_by_set = {}
        for rule in self.rules:
            if rule.set not in self.rules_by_set:
                self.rules_by_set[rule.set] = []
            self.rules_by_set[rule.set].append(rule)
    
    def _load_rules(self, rules_data: dict) -> List[Rule]:
        rules = []
        for rule_data in rules_data['rules']:
            rule = Rule(
                rule_id=rule_data['id'],
                set=rule_data.get('set', 0),
                antecedents=rule_data['antecedents'],
                consequent=rule_data['consequent'],
                description=rule_data.get('description', ''),
                cf=CF_CONFIG.get("rule_cf", {}).get(str(rule_data['id']), rule_data.get("cf", 1.0))
            )
            rules.append(rule)
        return rules


class BackwardChainingEngine:
    """Expert system with backward chaining inference and debug tracking"""
    
    def __init__(self, knowledge_base: KnowledgeBase):
        self.kb = knowledge_base
        self.facts: Dict[str, Fact] = {}  # Working memory
        self.executed_rules: List[int] = []
        self.debug_steps: List[DebugStep] = []  # Track all inference steps
        self.step_counter = 0
        self.goal_stack = []  # Track goal stack to detect cycles
        
    def reset(self):
        """Reset working memory and explanation"""
        self.facts = {}
        self.executed_rules = []
        self.debug_steps = []
        self.step_counter = 0
        self.goal_stack = []
    
    def add_debug_step(self, step_type: str, depth: int, message: str, 
                       rule_id: int = None, attribute: str = None, value: str = None):
        """Add a debug step with timestamp"""
        self.step_counter += 1
        self.debug_steps.append(DebugStep(
            type=step_type,
            depth=depth,
            message=message,
            rule_id=rule_id,
            attribute=attribute,
            value=value,
            timestamp=self.step_counter
        ))
    
    def assert_fact(self, attribute: str, value: str, derived: bool = False, rule_id: int = None, depth: int = 0):
        """Add a fact to working memory"""
        if attribute not in self.facts:
            self.facts[attribute] = Fact(attribute, value, derived=derived, rule_used=rule_id)
            if derived:
                self.add_debug_step('fact_derived', depth, 
                                   f"Derived fact: {attribute} = {value} using Rule {rule_id}",
                                   rule_id=rule_id, attribute=attribute, value=value)
            else:
                self.add_debug_step('fact_input', depth,
                                   f"User input: {attribute} = {value}",
                                   attribute=attribute, value=value)
            return True
        return False
    
    def get_fact(self, attribute: str) -> Optional[str]:
        """Retrieve fact value if exists"""
        if attribute in self.facts:
            return self.facts[attribute].value
        return None
    
    def check_antecedent(self, antecedent: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Check if an antecedent condition is satisfied. Returns (is_satisfied, actual_value)"""
        attr = antecedent['attr']
        target_value = antecedent['value']
        
        fact_value = self.get_fact(attr)
        if fact_value is None:
            return False, None
        
        return fact_value == target_value, fact_value
    
    def check_rule_antecedents(self, rule: Rule) -> Tuple[bool, List[str], Dict[str, str]]:
        """
        Check all antecedents of a rule.
        Returns (satisfied, missing_variables, current_values)
        """
        missing = []
        current_values = {}
        or_group_satisfied = False
        or_group_vars = []
        or_group_missing = []
        
        i = 0
        while i < len(rule.antecedents):
            ant = rule.antecedents[i]
            
            # Check for OR operator (current or next condition has 'or' operator)
            has_or = ant.get('operator') == 'or' or (i > 0 and rule.antecedents[i-1].get('operator') == 'or')
            
            if has_or:
                or_group_vars.append(ant)
                i += 1
                continue
            
            # If we have collected OR group conditions
            if or_group_vars:
                or_satisfied = False
                for or_ant in or_group_vars:
                    satisfied, value = self.check_antecedent(or_ant)
                    if satisfied:
                        or_satisfied = True
                        current_values[or_ant['attr']] = value
                        break
                    elif value is None:
                        or_group_missing.append(or_ant['attr'])
                
                if not or_satisfied:
                    missing.extend(or_group_missing)
                    return False, missing, current_values
                
                or_group_vars = []
                or_group_missing = []
                or_group_satisfied = False
                continue
            
            # Regular AND condition
            satisfied, value = self.check_antecedent(ant)
            if satisfied:
                current_values[ant['attr']] = value
                i += 1
            else:
                if value is None:
                    missing.append(ant['attr'])
                return False, missing, current_values
        
        # Handle remaining OR group at the end
        if or_group_vars:
            or_satisfied = False
            for or_ant in or_group_vars:
                satisfied, value = self.check_antecedent(or_ant)
                if satisfied:
                    or_satisfied = True
                    current_values[or_ant['attr']] = value
                    break
                elif value is None:
                    or_group_missing.append(or_ant['attr'])
            
            if not or_satisfied:
                missing.extend(or_group_missing)
                return False, missing, current_values
        
        return True, [], current_values
    
    def find_rules_for_goal(self, goal_attr: str, goal_value: str = None) -> List[Rule]:
        """Find rules that can derive the goal across all rule sets"""
        matching_rules = []
        for rule in self.kb.rules:
            if goal_attr in rule.consequent:
                if goal_value is None or rule.consequent[goal_attr] == goal_value:
                    matching_rules.append(rule)
        # Sort by set number (lower sets = more basic facts, higher sets = more complex)
        # This helps prove basic facts first
        matching_rules.sort(key=lambda r: (r.set, r.rule_id))
        return matching_rules
    
    def backward_chain(self, goal_attr: str, goal_value: str = None, depth: int = 0) -> bool:
        """
        Backward chaining algorithm to prove a goal with step tracking
        Returns True if goal can be proven
        """
        indent = "  " * depth
        
        # Check for cycles
        goal_key = f"{goal_attr}:{goal_value}" if goal_value else goal_attr
        if goal_key in self.goal_stack:
            self.add_debug_step('cycle_detected', depth,
                            f"Cycle detected. Already trying to prove {goal_key}",
                            attribute=goal_attr, value=goal_value)
            return False
        
        # Log goal attempt
        goal_display = f"{goal_attr} = {goal_value}" if goal_value else f"{goal_attr} = ?"
        self.add_debug_step('goal_attempt', depth, 
                        f"Proving: {goal_display}",
                        attribute=goal_attr, value=goal_value)
        
        # Push to goal stack
        self.goal_stack.append(goal_key)
        
        # Check if goal already exists in facts
        existing = self.get_fact(goal_attr)
        if existing is not None:
            if goal_value is None or existing == goal_value:
                self.add_debug_step('goal_found', depth, 
                                f"Goal already known: {goal_attr} = {existing}",
                                attribute=goal_attr, value=existing)
                self.goal_stack.pop()
                return True
            else:
                self.add_debug_step('goal_fail', depth,
                                f"Goal exists but value mismatch: {goal_attr} = {existing} (need {goal_value})",
                                attribute=goal_attr, value=existing)
                self.goal_stack.pop()
                return False
        
        # Find rules that can derive this goal
        rules = self.find_rules_for_goal(goal_attr, goal_value)
        
        if not rules:
            self.add_debug_step('no_rules', depth,
                            f"No rules found that can derive {goal_display}",
                            attribute=goal_attr, value=goal_value)
            self.goal_stack.pop()
            return False
        
        self.add_debug_step('rules_found', depth,
                        f"Found {len(rules)} rule(s) that can derive {goal_display}")
        
        # Try each rule
        for rule_index, rule in enumerate(rules):
            # Log rule attempt
            antecedent_summary = ", ".join([f"{a['attr']}={a['value']}" for a in rule.antecedents[:3]])
            if len(rule.antecedents) > 3:
                antecedent_summary += "..."
            
            self.add_debug_step('rule_attempt', depth,
                            f"Trying Rule {rule.rule_id} (Set {rule.set}): IF {antecedent_summary} THEN {goal_attr}={rule.consequent[goal_attr]}",
                            rule_id=rule.rule_id)
            
            # Check current satisfaction status
            satisfied, missing, current_vals = self.check_rule_antecedents(rule)
            
            if satisfied:
                # All antecedents satisfied - fire rule
                self.add_debug_step('rule_fire', depth,
                                f"Rule {rule.rule_id} antecedents satisfied. Firing rule.",
                                rule_id=rule.rule_id)
                for attr, val in rule.consequent.items():
                    self.assert_fact(attr, val, derived=True, rule_id=rule.rule_id, depth=depth)
                self.executed_rules.append(rule.rule_id)
                self.goal_stack.pop()
                return True
            else:
                # Try to prove missing antecedents
                if missing:
                    self.add_debug_step('rule_missing', depth,
                                    f"Rule {rule.rule_id} needs: {', '.join(missing)}",
                                    rule_id=rule.rule_id)
                    
                    # Store current facts before trying to prove missing antecedents
                    facts_before = set(self.facts.keys())
                    
                    # Try to prove each missing antecedent
                    all_proven = True
                    proven_antecedents = []
                    
                    for missing_attr in missing:
                        self.add_debug_step('subgoal', depth + 1,
                                        f"Establishing subgoal: {missing_attr}",
                                        attribute=missing_attr)
                        
                        # Try to prove this missing antecedent
                        if self.backward_chain(missing_attr, depth=depth + 1):
                            proven_antecedents.append(missing_attr)
                            self.add_debug_step('subgoal_success', depth + 1,
                                            f"Successfully proved {missing_attr} = {self.get_fact(missing_attr)}",
                                            attribute=missing_attr)
                        else:
                            all_proven = False
                            self.add_debug_step('subgoal_fail', depth + 1,
                                            f"Failed to prove {missing_attr}",
                                            attribute=missing_attr)
                            break
                    
                    if all_proven:
                        # Re-check the SAME rule after proving missing facts
                        self.add_debug_step('recheck_rule', depth,
                                        f"Re-checking Rule {rule.rule_id} after proving subgoals...",
                                        rule_id=rule.rule_id)
                        
                        satisfied, remaining_missing, _ = self.check_rule_antecedents(rule)
                        
                        if satisfied:
                            self.add_debug_step('rule_fire_after_subgoals', depth,
                                            f"Rule {rule.rule_id} now satisfied after proving subgoals.",
                                            rule_id=rule.rule_id)
                            for attr, val in rule.consequent.items():
                                self.assert_fact(attr, val, derived=True, rule_id=rule.rule_id, depth=depth)
                            self.executed_rules.append(rule.rule_id)
                            self.goal_stack.pop()
                            return True
                        else:
                            # CRITICAL FIX: If there are still missing antecedents but we've already
                            # proven some, we should recursively try to prove the remaining ones
                            # instead of giving up on this rule
                            if remaining_missing:
                                self.add_debug_step('rule_still_missing', depth,
                                                f"Rule {rule.rule_id} still missing: {', '.join(remaining_missing)}",
                                                rule_id=rule.rule_id)
                                
                                # Check which missing antecedents are new vs already attempted
                                remaining_to_prove = []
                                for missing_attr in remaining_missing:
                                    if missing_attr not in proven_antecedents:
                                        remaining_to_prove.append(missing_attr)
                                
                                if remaining_to_prove:
                                    self.add_debug_step('continuing_subgoals', depth,
                                                    f"Continuing to prove remaining missing: {', '.join(remaining_to_prove)}",
                                                    rule_id=rule.rule_id)
                                    
                                    # Continue trying to prove remaining missing antecedents
                                    still_all_proven = True
                                    for missing_attr in remaining_to_prove:
                                        self.add_debug_step('subgoal', depth + 1,
                                                        f"Establishing subgoal: {missing_attr}",
                                                        attribute=missing_attr)
                                        
                                        if self.backward_chain(missing_attr, depth=depth + 1):
                                            self.add_debug_step('subgoal_success', depth + 1,
                                                            f"Successfully proved {missing_attr} = {self.get_fact(missing_attr)}",
                                                            attribute=missing_attr)
                                        else:
                                            still_all_proven = False
                                            self.add_debug_step('subgoal_fail', depth + 1,
                                                            f"Failed to prove {missing_attr}",
                                                            attribute=missing_attr)
                                            break
                                    
                                    if still_all_proven:
                                        # Final re-check after proving all remaining
                                        satisfied, final_missing, _ = self.check_rule_antecedents(rule)
                                        if satisfied:
                                            self.add_debug_step('rule_fire_after_all_subgoals', depth,
                                                            f"Rule {rule.rule_id} finally satisfied after proving all subgoals.",
                                                            rule_id=rule.rule_id)
                                            for attr, val in rule.consequent.items():
                                                self.assert_fact(attr, val, derived=True, rule_id=rule.rule_id, depth=depth)
                                            self.executed_rules.append(rule.rule_id)
                                            self.goal_stack.pop()
                                            return True
                                        else:
                                            self.add_debug_step('rule_fail', depth,
                                                            f"Rule {rule.rule_id} still has missing: {', '.join(final_missing)}",
                                                            rule_id=rule.rule_id)
                                    else:
                                        self.add_debug_step('rule_fail', depth,
                                                        f"Rule {rule.rule_id} failed - could not prove remaining antecedents",
                                                        rule_id=rule.rule_id)
                                else:
                                    # All missing were already attempted but still missing - something wrong
                                    self.add_debug_step('rule_fail', depth,
                                                    f"Rule {rule.rule_id} failed - missing antecedents persist: {', '.join(remaining_missing)}",
                                                    rule_id=rule.rule_id)
                            else:
                                # No missing but rule not satisfied - shouldn't happen
                                self.add_debug_step('rule_fail', depth,
                                                f"Rule {rule.rule_id} failed - no missing but not satisfied",
                                                rule_id=rule.rule_id)
                    else:
                        # Failed to prove some antecedents, try next rule
                        self.add_debug_step('rule_fail', depth,
                                        f"Rule {rule.rule_id} failed - could not prove all antecedents",
                                        rule_id=rule.rule_id)
                        # Continue to next rule
                        continue
                else:
                    # No missing variables but rule not satisfied (shouldn't happen)
                    self.add_debug_step('rule_fail', depth,
                                    f"Rule {rule.rule_id} failed for unknown reason",
                                    rule_id=rule.rule_id)
        
        self.add_debug_step('goal_fail', depth, f"Could not prove {goal_display} after trying all rules")
        self.goal_stack.pop()
        return False
    
    def evaluate(self, user_inputs: Dict[str, str], goal: str = 'tingkat_resiko_dbd') -> Dict[str, Any]:
        """
        Main evaluation method using backward chaining with full debug tracking
        """
        self.reset()
        
        # Add user inputs as facts
        for attr, value in user_inputs.items():
            if attr in self.kb.all_variables:
                self.assert_fact(attr, value, derived=False, depth=0)
        
        # Perform backward chaining to prove goal
        self.add_debug_step('start', 0, f"Starting Backward Chaining to prove: {goal}")
        success = self.backward_chain(goal)
        
        # Add conclusion step
        if success:
            result_value = self.get_fact(goal)
            self.add_debug_step('conclusion', 0, 
                               f"CONCLUSION: {goal} = {result_value} (successfully proved)")
        else:
            self.add_debug_step('conclusion', 0,
                               f"CONCLUSION: Could not determine {goal} from given facts")
        
        # Get result
        result_value = self.get_fact(goal)
        
        # Also derive intermediate results for display
        potensi = self.get_fact('potensi_perkembangbiakan')
        iklim_val = self.get_fact('iklim')
        eksposur = self.get_fact('faktor_eksposur_manusia')
        
        return {
            'success': success,
            'tingkat_resiko_dbd': result_value,
            'potensi_perkembangbiakan': potensi,
            'iklim': iklim_val,
            'faktor_eksposur_manusia': eksposur,
            'executed_rules': self.executed_rules,
            'debug_steps': self.debug_steps,
            'all_facts': {k: v.value for k, v in self.facts.items()}
        }


class CertaintyFactorCalculator:
    def __init__(self, rules_data: Dict[str, Any], questions: Dict[str, Any], cf_config: Dict[str, Any]):
        self.rules_data = rules_data
        self.questions = questions
        self.rule_cf = cf_config.get("rule_cf", {})
        self.user_cf = cf_config.get("user_cf", {})
        self.threshold = float(cf_config.get("threshold", 0.5))

    @staticmethod
    def combine_cf(old_cf: float, new_cf: float) -> float:
        if old_cf >= 0 and new_cf >= 0:
            return old_cf + new_cf * (1 - old_cf)
        if old_cf < 0 and new_cf < 0:
            return old_cf + new_cf * (1 + old_cf)
        denominator = 1 - min(abs(old_cf), abs(new_cf))
        if denominator == 0:
            return 0
        return (old_cf + new_cf) / denominator

    @staticmethod
    def ordered_rules(rules: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        set_order = {2: 0, 3: 1, 4: 2, 1: 3}
        return sorted(rules, key=lambda item: (set_order.get(item.get("set"), 9), item.get("id", 0)))

    def seed_user_facts(self, user_inputs: Dict[str, str]) -> Dict[str, Dict[str, float]]:
        fact_cfs: Dict[str, Dict[str, float]] = {}
        for attr, value in user_inputs.items():
            cf = self.user_cf.get(attr, {}).get(value, 1.0)
            fact_cfs.setdefault(attr, {})[value] = float(cf)
        return fact_cfs

    def antecedent_cf(self, antecedent: Dict[str, Any], fact_cfs: Dict[str, Dict[str, float]]) -> Optional[float]:
        return fact_cfs.get(antecedent.get("attr"), {}).get(antecedent.get("value"))

    def premise_cf(self, antecedents: List[Dict[str, Any]], fact_cfs: Dict[str, Dict[str, float]]) -> Optional[float]:
        premise_values = []
        i = 0
        while i < len(antecedents):
            current = antecedents[i]
            is_or = current.get("operator") == "or"

            if is_or:
                group_values = []
                while i < len(antecedents):
                    item = antecedents[i]
                    group_values.append(item)
                    i += 1
                    if i >= len(antecedents) or antecedents[i].get("operator") != "or":
                        break

                cf_values = [
                    self.antecedent_cf(item, fact_cfs)
                    for item in group_values
                ]
                cf_values = [value for value in cf_values if value is not None]
                if not cf_values:
                    return None
                premise_values.append(max(cf_values))
                continue

            cf = self.antecedent_cf(current, fact_cfs)
            if cf is None:
                return None
            premise_values.append(cf)
            i += 1

        if not premise_values:
            return None
        return min(premise_values)

    def calculate(self, user_inputs: Dict[str, str], result: Dict[str, Any]) -> Dict[str, Any]:
        fact_cfs = self.seed_user_facts(user_inputs)
        fired_rules = []

        for rule in self.ordered_rules(self.rules_data.get("rules", [])):
            premise = self.premise_cf(rule.get("antecedents", []), fact_cfs)
            if premise is None:
                continue
            rule_id = str(rule.get("id"))
            rule_cf = float(self.rule_cf.get(rule_id, rule.get("cf", 1.0)))
            produced_cf = round(premise * rule_cf, 6)

            for attr, value in rule.get("consequent", {}).items():
                previous = fact_cfs.setdefault(attr, {}).get(value)
                if previous is None:
                    combined = produced_cf
                else:
                    combined = self.combine_cf(previous, produced_cf)
                fact_cfs[attr][value] = round(combined, 6)
                fired_rules.append({
                    "rule_id": int(rule.get("id")),
                    "attribute": attr,
                    "value": value,
                    "premise_cf": round(premise, 6),
                    "rule_cf": round(rule_cf, 6),
                    "produced_cf": produced_cf,
                    "combined_cf": fact_cfs[attr][value],
                })

        risk_level = result.get("tingkat_resiko_dbd")
        risk_cf = 0.0
        if risk_level:
            risk_cf = fact_cfs.get("tingkat_resiko_dbd", {}).get(risk_level, 0.0)

        intermediate_cf = {
            "potensi_perkembangbiakan": fact_cfs.get("potensi_perkembangbiakan", {}).get(result.get("potensi_perkembangbiakan"), 0.0),
            "kondisi_iklim": fact_cfs.get("iklim", {}).get(result.get("iklim"), 0.0),
            "faktor_eksposur": fact_cfs.get("faktor_eksposur_manusia", {}).get(result.get("faktor_eksposur_manusia"), 0.0),
        }

        return {
            "risk_cf": round(risk_cf, 6),
            "risk_percent": round(risk_cf * 100, 2),
            "threshold": self.threshold,
            "valid": risk_cf >= self.threshold,
            "intermediate_cf": {key: round(value, 6) for key, value in intermediate_cf.items()},
            "all_conclusions": fact_cfs,
            "fired_rules": fired_rules,
        }


# ============================================
# FLASK WEB APPLICATION
# ============================================

knowledge_base = KnowledgeBase(RULES_DATA)
engine = BackwardChainingEngine(knowledge_base)

@app.route('/')
def index():
    """Home page"""
    return render_template(
        'dbd_index.html',
        questions=QUESTIONS,
        rules_count=len(RULES_DATA['rules']),
        question_count=len(QUESTIONS)
    )

@app.route('/survey')
def survey():
    """Survey page"""
    return render_template('dbd_survey.html', questions=QUESTIONS)

@app.route('/result')
def result_page():
    """Result page loaded from browser storage"""
    return render_template('dbd_result.html')

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """Admin and dev login page"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').encode('utf-8')
        if username == ADMIN_USERNAME and bcrypt.checkpw(password, ADMIN_PASSWORD_HASH):
            response = make_response(redirect(request.args.get('next') or '/admin'))
            response.set_cookie(
                AUTH_COOKIE,
                create_jwt(username),
                max_age=TOKEN_MAX_AGE_SECONDS,
                httponly=True,
                samesite='Lax'
            )
            return response
        return render_template('dbd_login.html', error='Username atau password tidak valid.')
    if current_admin():
        return redirect('/admin')
    return render_template('dbd_login.html', error=None)

@app.route('/logout')
def logout_page():
    response = make_response(redirect('/login'))
    response.delete_cookie(AUTH_COOKIE)
    return response

@app.route('/api/evaluate', methods=['POST'])
def evaluate():
    """API endpoint for evaluation using backward chaining"""
    try:
        data = request.get_json()
        user_answers = data.get('answers', {})
        
        # Validate all required questions are answered
        required_questions = list(QUESTIONS.keys())
        for q in required_questions:
            if q not in user_answers or not user_answers[q]:
                return jsonify({'error': f'Please answer question: {q}'}), 400
            if user_answers[q] not in QUESTIONS[q].get('options', {}):
                return jsonify({'error': f'Invalid answer for question: {q}'}), 400
        
        # Run backward chaining expert system
        result = engine.evaluate(user_answers)
        cf_result = CertaintyFactorCalculator(RULES_DATA, QUESTIONS, CF_CONFIG).calculate(user_answers, result)
        
        # Add human-readable risk interpretation
        risk_levels = {
            'rendah': {'color': 'success', 'icon': '', 'message': 'Risiko DBD rendah. Kondisi cukup aman, tetap lakukan pemantauan berkala.'},
            'sedang': {'color': 'warning', 'icon': '', 'message': 'Risiko DBD sedang. Perlu peningkatan kewaspadaan dan pencegahan lingkungan.'},
            'tinggi': {'color': 'danger', 'icon': '', 'message': 'Risiko DBD tinggi. Segera lakukan tindakan pencegahan dan koordinasi lingkungan.'}
        }
        
        risk_info = risk_levels.get(result['tingkat_resiko_dbd'], risk_levels['rendah'])
        
        # Convert debug steps to serializable format
        debug_steps = []
        for step in result['debug_steps']:
            debug_steps.append({
                'type': step.type,
                'depth': step.depth,
                'message': step.message,
                'rule_id': step.rule_id,
                'attribute': step.attribute,
                'value': step.value,
                'timestamp': step.timestamp
            })
        
        return jsonify({
            'success': result['success'],
            'risk_level': result['tingkat_resiko_dbd'],
            'risk_color': risk_info['color'],
            'risk_icon': risk_info['icon'],
            'risk_message': risk_info['message'],
            'intermediate_results': {
                'potensi_perkembangbiakan': result['potensi_perkembangbiakan'],
                'kondisi_iklim': result['iklim'],
                'faktor_eksposur': result['faktor_eksposur_manusia']
            },
            'executed_rules': result['executed_rules'],
            'debug_steps': debug_steps,
            'all_facts': result['all_facts'],
            'cf': cf_result
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/explanation')
def explanation():
    """Legacy explanation page"""
    return redirect('/')

@app.route('/debug')
def debug_page():
    """Legacy debug page"""
    return redirect('/dev')

@app.route('/dev')
@admin_required
def dev_page():
    """Dev page with step-by-step visualization"""
    return render_template(
        'dbd_debug.html',
        questions=QUESTIONS,
        rules_count=len(RULES_DATA['rules'])
    )

@app.route('/admin')
@admin_required
def admin_page():
    """Admin page for dynamic rule and question management"""
    return render_template(
        'dbd_admin.html',
        questions=QUESTIONS,
        rules_count=len(RULES_DATA['rules'])
    )

@app.route('/api/admin/config')
@admin_required
def admin_config():
    rules_for_ui = []
    for rule in RULES_DATA.get('rules', []):
        item = dict(rule)
        item['cf'] = CF_CONFIG.get('rule_cf', {}).get(str(rule.get('id')), rule.get('cf', 1.0))
        rules_for_ui.append(item)
    return jsonify({
        'rules': rules_for_ui,
        'questions': QUESTIONS,
        'cf_config': CF_CONFIG,
        'input_variables': INPUT_VARIABLES,
        'derived_values': DERIVED_VALUES,
        'all_variables': ALL_VARIABLES,
    })

@app.route('/api/admin/rules', methods=['POST'])
@admin_required
def admin_save_rule():
    payload = request.get_json() or {}
    existing_ids = [int(rule.get('id')) for rule in RULES_DATA.get('rules', []) if 'id' in rule]
    try:
        cleaned_rule, cf = validate_rule(payload, QUESTIONS, existing_ids)
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400

    updated_rules = [rule for rule in RULES_DATA.get('rules', []) if int(rule.get('id')) != cleaned_rule['id']]
    updated_rules.append(cleaned_rule)
    updated_rules.sort(key=lambda item: (int(item.get('set', 0)), int(item.get('id', 0))))
    new_rules_data = {'rules': updated_rules}
    save_rules_data(new_rules_data)

    new_cf = load_cf_config()
    new_cf.setdefault('rule_cf', {})[str(cleaned_rule['id'])] = cf
    save_cf_config(new_cf)
    refresh_runtime_data()
    return jsonify({'success': True})

@app.route('/api/admin/rules/<int:rule_id>', methods=['DELETE'])
@admin_required
def admin_delete_rule(rule_id: int):
    updated_rules = [rule for rule in RULES_DATA.get('rules', []) if int(rule.get('id')) != rule_id]
    if len(updated_rules) == len(RULES_DATA.get('rules', [])):
        return jsonify({'error': 'Rule tidak ditemukan.'}), 404
    save_rules_data({'rules': updated_rules})
    new_cf = load_cf_config()
    new_cf.setdefault('rule_cf', {}).pop(str(rule_id), None)
    save_cf_config(new_cf)
    refresh_runtime_data()
    return jsonify({'success': True})

@app.route('/api/admin/questions/<fact_key>', methods=['POST'])
@admin_required
def admin_save_question(fact_key: str):
    if fact_key not in INPUT_VARIABLES:
        return jsonify({'error': 'Fakta input tidak valid.'}), 400

    payload = request.get_json() or {}
    candidate = json.loads(json.dumps(QUESTIONS))
    candidate[fact_key] = {
        'text': str(payload.get('text', '')).strip(),
        'options': payload.get('options', {}),
        'explanation': payload.get('explanation', {}),
    }
    errors = validate_questions(candidate, RULES_DATA)
    if errors:
        return jsonify({'error': '; '.join(errors)}), 400

    new_cf = load_cf_config()
    user_cf = new_cf.setdefault('user_cf', {})
    user_cf[fact_key] = {
        value: normalize_cf(payload.get('user_cf', {}).get(value, user_cf.get(fact_key, {}).get(value, 1.0)))
        for value in candidate[fact_key]['options'].keys()
    }
    save_questions(candidate)
    save_cf_config(new_cf)
    refresh_runtime_data()
    return jsonify({'success': True})

@app.route('/api/admin/cf/rule/<int:rule_id>', methods=['POST'])
@admin_required
def admin_save_rule_cf(rule_id: int):
    payload = request.get_json() or {}
    if not any(int(rule.get('id')) == rule_id for rule in RULES_DATA.get('rules', [])):
        return jsonify({'error': 'Rule tidak ditemukan.'}), 404
    try:
        cf = normalize_cf(payload.get('cf'))
    except ValueError as exc:
        return jsonify({'error': str(exc)}), 400
    new_cf = load_cf_config()
    new_cf.setdefault('rule_cf', {})[str(rule_id)] = cf
    save_cf_config(new_cf)
    refresh_runtime_data()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
