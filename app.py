# app.py - Fixed Backward Chaining with Proper Multi-Level Inference

import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from flask import Flask, render_template, request, jsonify, session
from enums import QUESTIONS

app = Flask(__name__)
app.secret_key = 'dbd-expert-system-secret-key'

# Load rules from JSON file
with open('rules.json', 'r', encoding='utf-8') as f:
    RULES_DATA = json.load(f)


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
        self.all_variables = [
            'genangan_air_terbuka', 'durasi_genangan_air', 'keberadaan_jentik',
            'nyamuk_aedes', 'frekuensi_hujan', 'intensitas_hujan',
            'mobilitas_penduduk', 'kepadatan_penduduk', 'kondisi_lingkungan_sekitar',
            'potensi_perkembangbiakan', 'iklim', 'faktor_eksposur_manusia',
            'tingkat_resiko_dbd'
        ]
        
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
                description=rule_data.get('description', '')
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
                                   f"✓ Derived: {attribute} = {value} using Rule {rule_id}",
                                   rule_id=rule_id, attribute=attribute, value=value)
            else:
                self.add_debug_step('fact_input', depth,
                                   f"📝 User input: {attribute} = {value}",
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
                            f"⚠️ Cycle detected! Already trying to prove {goal_key}",
                            attribute=goal_attr, value=goal_value)
            return False
        
        # Log goal attempt
        goal_display = f"{goal_attr} = {goal_value}" if goal_value else f"{goal_attr} = ?"
        self.add_debug_step('goal_attempt', depth, 
                        f"🎯 Proving: {goal_display}",
                        attribute=goal_attr, value=goal_value)
        
        # Push to goal stack
        self.goal_stack.append(goal_key)
        
        # Check if goal already exists in facts
        existing = self.get_fact(goal_attr)
        if existing is not None:
            if goal_value is None or existing == goal_value:
                self.add_debug_step('goal_found', depth, 
                                f"✅ Goal already known: {goal_attr} = {existing}",
                                attribute=goal_attr, value=existing)
                self.goal_stack.pop()
                return True
            else:
                self.add_debug_step('goal_fail', depth,
                                f"❌ Goal exists but value mismatch: {goal_attr} = {existing} (need {goal_value})",
                                attribute=goal_attr, value=existing)
                self.goal_stack.pop()
                return False
        
        # Find rules that can derive this goal
        rules = self.find_rules_for_goal(goal_attr, goal_value)
        
        if not rules:
            self.add_debug_step('no_rules', depth,
                            f"❌ No rules found that can derive {goal_display}",
                            attribute=goal_attr, value=goal_value)
            self.goal_stack.pop()
            return False
        
        self.add_debug_step('rules_found', depth,
                        f"📋 Found {len(rules)} rule(s) that can derive {goal_display}")
        
        # Try each rule
        for rule_index, rule in enumerate(rules):
            # Log rule attempt
            antecedent_summary = ", ".join([f"{a['attr']}={a['value']}" for a in rule.antecedents[:3]])
            if len(rule.antecedents) > 3:
                antecedent_summary += "..."
            
            self.add_debug_step('rule_attempt', depth,
                            f"🔍 Trying Rule {rule.rule_id} (Set {rule.set}): IF {antecedent_summary} THEN {goal_attr}={rule.consequent[goal_attr]}",
                            rule_id=rule.rule_id)
            
            # Check current satisfaction status
            satisfied, missing, current_vals = self.check_rule_antecedents(rule)
            
            if satisfied:
                # All antecedents satisfied - fire rule
                self.add_debug_step('rule_fire', depth,
                                f"✅ Rule {rule.rule_id} antecedents satisfied! Firing rule.",
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
                                    f"⚠️ Rule {rule.rule_id} needs: {', '.join(missing)}",
                                    rule_id=rule.rule_id)
                    
                    # Store current facts before trying to prove missing antecedents
                    facts_before = set(self.facts.keys())
                    
                    # Try to prove each missing antecedent
                    all_proven = True
                    proven_antecedents = []
                    
                    for missing_attr in missing:
                        self.add_debug_step('subgoal', depth + 1,
                                        f"📌 Establishing subgoal: {missing_attr}",
                                        attribute=missing_attr)
                        
                        # Try to prove this missing antecedent
                        if self.backward_chain(missing_attr, depth=depth + 1):
                            proven_antecedents.append(missing_attr)
                            self.add_debug_step('subgoal_success', depth + 1,
                                            f"✅ Successfully proved {missing_attr} = {self.get_fact(missing_attr)}",
                                            attribute=missing_attr)
                        else:
                            all_proven = False
                            self.add_debug_step('subgoal_fail', depth + 1,
                                            f"❌ Failed to prove {missing_attr}",
                                            attribute=missing_attr)
                            break
                    
                    if all_proven:
                        # Re-check the SAME rule after proving missing facts
                        self.add_debug_step('recheck_rule', depth,
                                        f"🔄 Re-checking Rule {rule.rule_id} after proving subgoals...",
                                        rule_id=rule.rule_id)
                        
                        satisfied, remaining_missing, _ = self.check_rule_antecedents(rule)
                        
                        if satisfied:
                            self.add_debug_step('rule_fire_after_subgoals', depth,
                                            f"✅ Rule {rule.rule_id} now satisfied after proving subgoals!",
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
                                                f"⚠️ Rule {rule.rule_id} still missing: {', '.join(remaining_missing)}",
                                                rule_id=rule.rule_id)
                                
                                # Check which missing antecedents are new vs already attempted
                                remaining_to_prove = []
                                for missing_attr in remaining_missing:
                                    if missing_attr not in proven_antecedents:
                                        remaining_to_prove.append(missing_attr)
                                
                                if remaining_to_prove:
                                    self.add_debug_step('continuing_subgoals', depth,
                                                    f"🔄 Continuing to prove remaining missing: {', '.join(remaining_to_prove)}",
                                                    rule_id=rule.rule_id)
                                    
                                    # Continue trying to prove remaining missing antecedents
                                    still_all_proven = True
                                    for missing_attr in remaining_to_prove:
                                        self.add_debug_step('subgoal', depth + 1,
                                                        f"📌 Establishing subgoal: {missing_attr}",
                                                        attribute=missing_attr)
                                        
                                        if self.backward_chain(missing_attr, depth=depth + 1):
                                            self.add_debug_step('subgoal_success', depth + 1,
                                                            f"✅ Successfully proved {missing_attr} = {self.get_fact(missing_attr)}",
                                                            attribute=missing_attr)
                                        else:
                                            still_all_proven = False
                                            self.add_debug_step('subgoal_fail', depth + 1,
                                                            f"❌ Failed to prove {missing_attr}",
                                                            attribute=missing_attr)
                                            break
                                    
                                    if still_all_proven:
                                        # Final re-check after proving all remaining
                                        satisfied, final_missing, _ = self.check_rule_antecedents(rule)
                                        if satisfied:
                                            self.add_debug_step('rule_fire_after_all_subgoals', depth,
                                                            f"✅ Rule {rule.rule_id} finally satisfied after proving all subgoals!",
                                                            rule_id=rule.rule_id)
                                            for attr, val in rule.consequent.items():
                                                self.assert_fact(attr, val, derived=True, rule_id=rule.rule_id, depth=depth)
                                            self.executed_rules.append(rule.rule_id)
                                            self.goal_stack.pop()
                                            return True
                                        else:
                                            self.add_debug_step('rule_fail', depth,
                                                            f"❌ Rule {rule.rule_id} still has missing: {', '.join(final_missing)}",
                                                            rule_id=rule.rule_id)
                                    else:
                                        self.add_debug_step('rule_fail', depth,
                                                        f"❌ Rule {rule.rule_id} failed - could not prove remaining antecedents",
                                                        rule_id=rule.rule_id)
                                else:
                                    # All missing were already attempted but still missing - something wrong
                                    self.add_debug_step('rule_fail', depth,
                                                    f"❌ Rule {rule.rule_id} failed - missing antecedents persist: {', '.join(remaining_missing)}",
                                                    rule_id=rule.rule_id)
                            else:
                                # No missing but rule not satisfied - shouldn't happen
                                self.add_debug_step('rule_fail', depth,
                                                f"❌ Rule {rule.rule_id} failed - no missing but not satisfied",
                                                rule_id=rule.rule_id)
                    else:
                        # Failed to prove some antecedents, try next rule
                        self.add_debug_step('rule_fail', depth,
                                        f"❌ Rule {rule.rule_id} failed - could not prove all antecedents",
                                        rule_id=rule.rule_id)
                        # Continue to next rule
                        continue
                else:
                    # No missing variables but rule not satisfied (shouldn't happen)
                    self.add_debug_step('rule_fail', depth,
                                    f"❌ Rule {rule.rule_id} failed for unknown reason",
                                    rule_id=rule.rule_id)
        
        self.add_debug_step('goal_fail', depth, f"❌ Could not prove {goal_display} after trying all rules")
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
        self.add_debug_step('start', 0, f"🚀 Starting Backward Chaining to prove: {goal}")
        success = self.backward_chain(goal)
        
        # Add conclusion step
        if success:
            result_value = self.get_fact(goal)
            self.add_debug_step('conclusion', 0, 
                               f"🏁 CONCLUSION: {goal} = {result_value} (Successfully proved!)")
        else:
            self.add_debug_step('conclusion', 0,
                               f"🏁 CONCLUSION: Could not determine {goal} from given facts")
        
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


# ============================================
# FLASK WEB APPLICATION
# ============================================

knowledge_base = KnowledgeBase(RULES_DATA)
engine = BackwardChainingEngine(knowledge_base)

@app.route('/')
def index():
    """Home page"""
    return render_template('dbd_index.html', questions=QUESTIONS)

@app.route('/survey')
def survey():
    """Survey page with all questions"""
    return render_template('dbd_survey.html', questions=QUESTIONS)

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
        
        # Run backward chaining expert system
        result = engine.evaluate(user_answers)
        
        # Add human-readable risk interpretation
        risk_levels = {
            'rendah': {'color': 'success', 'icon': '🟢', 'message': 'Risiko DBD Rendah - Kondisi cukup aman, tetap waspada'},
            'sedang': {'color': 'warning', 'icon': '🟡', 'message': 'Risiko DBD Sedang - Perlu peningkatan kewaspadaan'},
            'tinggi': {'color': 'danger', 'icon': '🔴', 'message': 'Risiko DBD Tinggi - Segera lakukan tindakan pencegahan!'}
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
            'all_facts': result['all_facts']
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/explanation')
def explanation():
    """Explanation page showing how backward chaining works"""
    return render_template('dbd_explanation.html')

@app.route('/debug')
def debug_page():
    """Debug page with step-by-step visualization"""
    return render_template('dbd_debug.html', questions=QUESTIONS)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)