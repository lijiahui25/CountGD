"""TPC-268 taxonomy registry. Node identity is (rank, official local ID).

Only exact normalized names and documented explicit aliases are resolved. Public
labels are available for parsing; training prototypes/edges use train paths only.
"""
import hashlib
import json
import unicodedata
from pathlib import Path

RANKS = ('Kingdom', 'Phylum', 'Class', 'Order', 'Family', 'Genus', 'Species')


def normalized_name(name):
    # Hybrid marker omission is a spelling normalization, not a genus fallback.
    return ' '.join(unicodedata.normalize('NFKC', name).replace('_', ' ')
                    .replace('×', ' ').casefold().split())


def read_split(path):
    paths = [x.strip().replace('\\', '/') for x in Path(path).read_text().splitlines() if x.strip()]
    if len(paths) != len(set(paths)):
        raise ValueError(f'Duplicate paths in {path}')
    for p in paths:
        if len(p.split('/')) != 3 or '..' in p.split('/') or p.startswith('/'):
            raise ValueError(f'Invalid relative image path: {p}')
    return paths


class TaxonomyRegistry:
    def __init__(self, ids_file, vectors_file, train_split, aliases_file=None, excluded_paths=()):
        self.ids = json.loads(Path(ids_file).read_text())
        self.vectors = json.loads(Path(vectors_file).read_text())
        self.aliases = json.loads(Path(aliases_file).read_text()) if aliases_file else {}
        self.reverse = [{int(v): k for k, v in self.ids[r].items()} for r in RANKS]
        for rank, rev in zip(RANKS, self.reverse):
            if len(rev) != len(self.ids[rank]):
                raise ValueError(f'Non-unique IDs at rank {rank}')
        self.lookup = {}
        for species in self.vectors:
            key = normalized_name(species)
            if key in self.lookup:
                raise ValueError(f'Ambiguous normalized species: {species}')
            self.lookup[key] = species
        for alias, entry in self.aliases.items():
            if not entry.get('evidence') or entry['canonical'] not in self.vectors:
                raise ValueError(f'Alias needs canonical name and evidence: {alias}')
            self.lookup[normalized_name(alias)] = entry['canonical']
        keys = [(l, i) for l, rev in enumerate(self.reverse) for i in sorted(rev)]
        self.uid = {key: i for i, key in enumerate(keys)}
        self.nodes = {}
        self.parent = {}
        self.paths = {}
        for species, local_ids in self.vectors.items():
            if len(local_ids) != 7:
                raise ValueError(f'Not a seven-rank path: {species}')
            uids = [self.uid[(l, int(i))] for l, i in enumerate(local_ids)]
            names = [self.reverse[l][int(i)] for l, i in enumerate(local_ids)]
            self.paths[species] = uids
            for l, u in enumerate(uids):
                prefix = 'A biological taxon classified as ' + ', '.join(names[:l + 1]) + '.'
                if u in self.nodes and self.nodes[u]['text'] != prefix:
                    raise ValueError(f'Conflicting taxonomy prefix/parent for {RANKS[l]} {names[l]}')
                self.nodes[u] = {'rank': l, 'local_id': int(local_ids[l]), 'name': names[l], 'text': prefix}
                if l:
                    if u in self.parent and self.parent[u] != uids[l - 1]:
                        raise ValueError(f'Conflicting parent for {names[l]}')
                    self.parent[u] = uids[l - 1]
        self.train_paths = [p for p in read_split(train_split) if p not in set(excluded_paths)]
        self.train_nodes = [set() for _ in RANKS]
        self.train_edges = set()
        self.train_units = set()
        self.organs = sorted({p.split('/')[1] for p in self.train_paths})
        # organ IDs are metadata only; unknown eval organs receive -1.
        for p in self.train_paths:
            species = self.resolve(p.split('/')[0])
            if species is None:
                continue
            path = self.paths[species]
            for l, u in enumerate(path):
                self.train_nodes[l].add(u)
            self.train_edges.update(zip(path[:-1], path[1:]))
            self.train_units.add((species, p.split('/')[1]))
        payload = {'ids': self.ids, 'vectors': self.vectors, 'aliases': self.aliases,
                   'train_paths': self.train_paths}
        self.fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def resolve(self, original):
        return self.lookup.get(normalized_name(original))

    def metadata(self, relative_path):
        original, organ, _ = relative_path.split('/')
        canonical = self.resolve(original)
        if canonical is None:
            return original.replace('_', ' '), organ, [-1] * 7, [-1] * 7, [False] * 7
        return canonical, organ, self.vectors[canonical], self.paths[canonical], [True] * 7

    def report(self, paths):
        missing = sorted({p.split('/')[0] for p in paths if self.resolve(p.split('/')[0]) is None})
        resolved = sum(self.resolve(p.split('/')[0]) is not None for p in paths)
        return {'images': len(paths), 'resolved_images': resolved,
                'coverage': resolved / max(len(paths), 1), 'species': len({p.split('/')[0] for p in paths}),
                'unresolved_species': missing, 'registry_fingerprint': self.fingerprint}


def registry_from_args(args):
    return TaxonomyRegistry(args.tpc268_taxonomy_ids_file, args.tpc268_taxonomy_vectors_file,
                            args.tpc268_train_split, args.tpc268_species_aliases_file,
                            getattr(args, "tpc268_excluded_paths", ()))
