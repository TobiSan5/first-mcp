"""
Smart tag mapping implementation for tinydb_memorize enhancement.
Implements the intelligent tag consolidation algorithm.

TODO: 
- Test with real instance data
- Integrate into tinydb_memorize function
- Add comprehensive logging
- Handle edge cases for malformed input
"""

from typing import List, Dict, Any, Tuple
from .tag_tools import tinydb_find_similar_tags, _generate_embedding, _cosine_similarity


def smart_tag_mapping(input_tags: List[str], content: str, max_tags: int = 3) -> Dict[str, Any]:
    """
    Implement smart tag mapping algorithm:
    1. For each input tag, find similar existing tags
    2. Auto-replace if similarity > 0.9
    3. Add to candidates if similarity > 0.75
    4. Select top 3 tags based on content similarity
    5. Return mapping results and transparency info
    
    Args:
        input_tags: List of tags provided by user
        content: Memory content for context-based selection
        max_tags: Maximum number of tags to return (default: 3)
        
    Returns:
        Dictionary with final tags, mapping info, and transparency details
    """
    if not input_tags:
        return {
            "final_tags": [],
            "mapping_applied": False,
            "transparency_info": "No tags provided"
        }
    
    # Step 1: Process each input tag
    final_tags = []
    candidates = []  # (tag, similarity_score, source_info)
    mapping_log = []
    auto_replacements = 0
    
    try:
        for input_tag in input_tags:
            input_tag = input_tag.strip().lower()
            if not input_tag:
                continue
                
            # Find similar existing tags
            similar_result = tinydb_find_similar_tags(input_tag, limit=5, min_similarity=0.7)
            
            if similar_result.get('success') and similar_result.get('similar_tags'):
                similar_tags = similar_result['similar_tags']
                
                # Check for auto-replacement (>0.9 similarity)
                auto_replaced = False
                for similar in similar_tags:
                    similarity = similar.get('similarity', 0)
                    existing_tag = similar.get('tag', '')
                    
                    if similarity > 0.9:
                        # Auto-replace with most similar existing tag
                        final_tags.append(existing_tag)
                        mapping_log.append(f"Auto-replaced '{input_tag}' → '{existing_tag}' (similarity: {similarity:.3f})")
                        auto_replacements += 1
                        auto_replaced = True
                        break
                
                if not auto_replaced:
                    # Add to candidates if >0.75 similarity
                    for similar in similar_tags:
                        similarity = similar.get('similarity', 0)
                        existing_tag = similar.get('tag', '')
                        usage_count = similar.get('usage_count', 0)
                        
                        if similarity > 0.75:
                            candidates.append((existing_tag, similarity, f"similar to '{input_tag}'", usage_count))
                    
                    # Also add original tag as candidate with lower priority
                    candidates.append((input_tag, 0.5, "original", 0))
            else:
                # No similar tags found, add original as candidate
                candidates.append((input_tag, 0.5, "original", 0))
        
        # Step 2: Content-based selection for remaining slots
        remaining_slots = max_tags - len(final_tags)
        
        if remaining_slots > 0 and candidates:
            # Generate content embedding for similarity comparison
            content_embedding = _generate_embedding(content)
            
            if content_embedding:
                # Score candidates based on content similarity
                scored_candidates = []
                for tag, tag_similarity, source, usage in candidates:
                    tag_embedding = _generate_embedding(tag)
                    if tag_embedding:
                        content_similarity = _cosine_similarity(content_embedding, tag_embedding)
                        # Combined score: tag similarity + content similarity + usage bonus
                        usage_bonus = min(usage * 0.01, 0.1)  # Small bonus for frequently used tags
                        combined_score = (tag_similarity * 0.4) + (content_similarity * 0.5) + usage_bonus
                        scored_candidates.append((tag, combined_score, source, tag_similarity, content_similarity))
                    else:
                        # Fallback to tag similarity only
                        scored_candidates.append((tag, tag_similarity, source, tag_similarity, 0))
                
                # Sort by combined score and take top candidates
                scored_candidates.sort(key=lambda x: x[1], reverse=True)
                
                for tag, combined_score, source, tag_sim, content_sim in scored_candidates[:remaining_slots]:
                    if tag not in final_tags:  # Avoid duplicates
                        final_tags.append(tag)
                        if source != "original":
                            mapping_log.append(f"Selected '{tag}' (content sim: {content_sim:.3f}, {source})")
            else:
                # Fallback: sort by tag similarity and usage
                candidates.sort(key=lambda x: (x[1], x[3]), reverse=True)
                for tag, similarity, source, usage in candidates[:remaining_slots]:
                    if tag not in final_tags:
                        final_tags.append(tag)
                        if source != "original":
                            mapping_log.append(f"Selected '{tag}' (fallback, {source})")
        
        # Step 3: Prepare transparency info
        mapping_applied = len(mapping_log) > 0
        transparency_info = ""
        
        if mapping_applied:
            transparency_info = f"Smart tag mapping applied: {len(mapping_log)} adjustments. "
            if auto_replacements > 0:
                transparency_info += f"{auto_replacements} auto-replacements (>90% similarity). "
            transparency_info += "See mapping_log for details."
        else:
            transparency_info = "No tag mapping needed - using original tags"
        
        return {
            "final_tags": final_tags[:max_tags],  # Ensure we don't exceed max
            "mapping_applied": mapping_applied,
            "transparency_info": transparency_info,
            "mapping_log": mapping_log,
            "auto_replacements": auto_replacements,
            "original_tags": input_tags,
            "candidates_considered": len(candidates)
        }
        
    except Exception as e:
        # Fallback to original tags on error
        return {
            "final_tags": input_tags[:max_tags],
            "mapping_applied": False,
            "transparency_info": f"Tag mapping failed ({str(e)}), using original tags",
            "error": str(e)
        }


if __name__ == "__main__":
    """Test the smart tag mapping with sample data."""
    print("=== TESTING SMART TAG MAPPING ===")
    print()
    
    test_cases = [
        {
            "tags": ["supplement", "health", "brain-fog", "neuroprotection", "cognitive"],
            "content": "Started taking Lion's Mane mushroom supplement for cognitive enhancement and brain fog reduction.",
            "description": "Health supplement memory (5 tags → 3 expected)"
        },
        {
            "tags": ["programming", "python", "project"],
            "content": "Working on the first-mcp Python package for MCP server development.",
            "description": "Programming project (3 tags, should map well)"
        },
        {
            "tags": ["run", "training", "intervals", "performance", "cardio"],
            "content": "Completed 5x4 minute interval training session with good heart rate response.",
            "description": "Running training (5 tags → 3 expected)"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test {i}: {test_case['description']}")
        print(f"Input tags: {test_case['tags']}")
        
        result = smart_tag_mapping(test_case['tags'], test_case['content'])
        
        print(f"Final tags: {result['final_tags']}")
        print(f"Mapping applied: {result['mapping_applied']}")
        print(f"Transparency: {result['transparency_info']}")
        
        if result.get('mapping_log'):
            print("Mapping log:")
            for log_entry in result['mapping_log']:
                print(f"  - {log_entry}")
        
        print()