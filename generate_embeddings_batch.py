#!/usr/bin/env python3
"""
Script to generate missing embeddings in batches with proper rate limiting.
"""

import sys
import time
sys.path.append('src')

from first_mcp.memory.tag_tools import tinydb_embedding_stats, _generate_embedding
from first_mcp.memory.database import get_tags_tinydb
from tinydb import Query
from datetime import datetime

def generate_embeddings_batch(batch_size=20, delay=0.5, max_batches=None):
    """Generate embeddings in small batches with delays."""
    
    # Get current stats
    stats = tinydb_embedding_stats()
    print(f"Starting batch embedding generation:")
    print(f"  Total tags: {stats['total_tags']}")
    print(f"  Missing embeddings: {stats['tags_without_embeddings']}")
    print(f"  Batch size: {batch_size}, Delay: {delay}s between batches")
    if max_batches:
        print(f"  Max batches: {max_batches}")
    print()
    
    try:
        tags_db = get_tags_tinydb()
        tags_table = tags_db.table('tags')
        Record = Query()
        
        # Find tags without embeddings
        tags_without_embeddings = tags_table.search(
            (Record.embedding == []) | (~Record.embedding.exists())
        )
        
        if not tags_without_embeddings:
            print("No tags need embeddings!")
            return
        
        total_to_process = len(tags_without_embeddings)
        processed = 0
        generated = 0
        failed = 0
        
        print(f"Found {total_to_process} tags needing embeddings")
        print("Processing in batches...")
        print()
        
        # Process in batches
        for i in range(0, len(tags_without_embeddings), batch_size):
            batch = tags_without_embeddings[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(tags_without_embeddings) + batch_size - 1) // batch_size
            
            # Check if we've reached max batches
            if max_batches and batch_num > max_batches:
                print(f"Reached maximum batch limit ({max_batches})")
                break
            
            print(f"Batch {batch_num}/{total_batches} ({len(batch)} tags):")
            
            for tag_record in batch:
                tag_name = tag_record.get('tag', '')
                
                try:
                    # Generate embedding
                    embedding = _generate_embedding(tag_name)
                    
                    if embedding:
                        # Update the tag with embedding
                        tags_table.update(
                            {
                                'embedding': embedding,
                                'embedding_generated_at': datetime.now().isoformat(),
                                'embedding_model': 'text-embedding-004'
                            },
                            Record.tag == tag_name
                        )
                        generated += 1
                        print(f"  ✓ {tag_name}")
                    else:
                        failed += 1
                        print(f"  ✗ {tag_name} (failed)")
                        
                except Exception as e:
                    failed += 1
                    print(f"  ✗ {tag_name} (error: {str(e)[:50]}...)")
                
                processed += 1
            
            # Progress update
            remaining = total_to_process - processed
            print(f"  Progress: {processed}/{total_to_process} processed, {generated} generated, {failed} failed")
            
            # Delay between batches (except for last batch)
            if i + batch_size < len(tags_without_embeddings):
                print(f"  Waiting {delay}s before next batch... ({remaining} remaining)")
                time.sleep(delay)
            
            print()
        
        tags_db.close()
        
        print("=" * 50)
        print("FINAL RESULTS:")
        print(f"  Total processed: {processed}")
        print(f"  Successfully generated: {generated}")
        print(f"  Failed: {failed}")
        print(f"  Success rate: {(generated/processed)*100:.1f}%")
        
        # Get updated stats
        final_stats = tinydb_embedding_stats()
        print(f"  Tags with embeddings now: {final_stats['tags_with_embeddings']}")
        print(f"  Coverage: {final_stats['coverage_percent']}%")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import sys
    
    # Allow command line arguments for batch size and max batches
    batch_size = 20
    max_batches = None
    
    if len(sys.argv) > 1:
        max_batches = int(sys.argv[1])
    if len(sys.argv) > 2:
        batch_size = int(sys.argv[2])
    
    generate_embeddings_batch(batch_size=batch_size, delay=0.5, max_batches=max_batches)