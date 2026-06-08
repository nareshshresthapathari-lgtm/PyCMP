#!/usr/bin/env python3
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


class AbstractItemset:
    def size(self) -> int:
        raise NotImplementedError

    def getAbsoluteSupport(self) -> int:
        raise NotImplementedError

    def getRelativeSupport(self, nbObject: int) -> float:
        raise NotImplementedError

    def contains(self, item: int) -> bool:
        raise NotImplementedError

    def print(self) -> None:
        print(str(self), end="")


class AbstractOrderedItemset(AbstractItemset):
    def get(self, position: int) -> int:
        raise NotImplementedError

    def getLastItem(self) -> int:
        return self.get(self.size() - 1)

    def __str__(self) -> str:
        if self.size() == 0:
            return "EMPTYSET"
        r = []
        for i in range(self.size()):
            r.append(str(self.get(i)))
            r.append(" ")
        return "".join(r)

    def getRelativeSupport(self, nbObject: int) -> float:
        return float(self.getAbsoluteSupport()) / float(nbObject)

    def contains(self, item: int) -> bool:
        for i in range(self.size()):
            gi = self.get(i)
            if gi == item:
                return True
            elif gi > item:
                return False
        return False

    def containsAll(self, itemset2: "AbstractOrderedItemset") -> bool:
        if self.size() < itemset2.size():
            return False
        i = 0
        for j in range(itemset2.size()):
            found = False
            while (not found) and i < self.size():
                if self.get(i) == itemset2.get(j):
                    found = True
                elif self.get(i) > itemset2.get(j):
                    return False
                i += 1
            if not found:
                return False
        return True

    def isEqualTo(self, other) -> bool:
        if hasattr(other, "size"):
            if self.size() != other.size():
                return False
            for i in range(other.size()):
                if other.get(i) != self.get(i):
                    return False
            return True
        arr = other
        if self.size() != len(arr):
            return False
        for i, v in enumerate(arr):
            if self.get(i) != v:
                return False
        return True

    def allTheSameExceptLastItemV2(self, itemset2: "AbstractOrderedItemset") -> bool:
        if itemset2.size() != self.size():
            return False
        for i in range(self.size() - 1):
            if self.get(i) != itemset2.get(i):
                return False
        return True

    def allTheSameExceptLastItem(self, itemset2: "AbstractOrderedItemset") -> Optional[int]:
        if itemset2.size() != self.size():
            return None
        for i in range(self.size()):
            if i == self.size() - 1:
                if self.get(i) >= itemset2.get(i):
                    return None
            elif self.get(i) != itemset2.get(i):
                return None
        return itemset2.get(itemset2.size() - 1)


@dataclass(eq=False)
class Itemset(AbstractOrderedItemset):
    itemset: List[int] = field(default_factory=list)
    transactionsIds: Set[int] = field(default_factory=set)

    def __init__(self, items=None):
        if items is None:
            self.itemset = []
        elif isinstance(items, int):
            self.itemset = [items]
        else:
            self.itemset = list(items)
        self.transactionsIds = set()

    def getAbsoluteSupport(self) -> int:
        return len(self.transactionsIds)

    def getItems(self) -> List[int]:
        return self.itemset

    def get(self, index: int) -> int:
        return self.itemset[index]

    def setTIDs(self, listTransactionIds: Set[int]) -> None:
        self.transactionsIds = set(listTransactionIds)

    def size(self) -> int:
        return len(self.itemset)

    def getTransactionsIds(self) -> Set[int]:
        return self.transactionsIds

    def cloneItemSetMinusAnItemset(self, itemsetToNotKeep: "Itemset") -> "Itemset":
        return Itemset([x for x in self.itemset if not itemsetToNotKeep.contains(x)])

    def cloneItemSetMinusOneItem(self, itemsetToRemove: int) -> "Itemset":
        return Itemset([x for x in self.itemset if x != itemsetToRemove])

    def __hash__(self) -> int:
        return hash(tuple(self.itemset))

    def __eq__(self, other) -> bool:
        return isinstance(other, Itemset) and self.itemset == other.itemset


class AlgoINDIRECT:
    def __init__(self):
        self.mapItemTIDS: Dict[int, Set[int]] = {}
        self.minSuppRelative = 0
        self.minconf = 0.0
        self.tsRelative = 0.0
        self.startTimestamp = 0
        self.endTimeStamp = 0
        self.writer = None
        self.ruleCount = 0
        self.tidcount = 0

    def runAlgorithm(self, input_path: str, output_path: str, minsup: float, ts: float, minconf: float):
        self.startTimestamp = int(time.time() * 1000)
        self.writer = open(output_path, "w", encoding="utf-8")
        self.minconf = minconf
        self.ruleCount = 0

        self.mapItemTIDS = {}
        self.tidcount = 0

        with open(input_path, "r", encoding="utf-8") as reader:
            for line in reader:
                line = line.strip()
                if (not line) or line[0] in "#%@":
                    continue
                for stringItem in line.split(" "):
                    item = int(stringItem)
                    tids = self.mapItemTIDS.get(item)
                    if tids is None:
                        tids = set()
                        self.mapItemTIDS[item] = tids
                    tids.add(self.tidcount)
                self.tidcount += 1

        self.minSuppRelative = int(math.ceil(minsup * self.tidcount))
        self.tsRelative = int(math.ceil(ts * self.tidcount))

        level: List[Itemset] = []
        for item in sorted(list(self.mapItemTIDS.keys())):
            tids = self.mapItemTIDS[item]
            if len(tids) >= self.minSuppRelative:
                itemset = Itemset(item)
                itemset.setTIDs(tids)
                level.append(itemset)

        level.sort(key=lambda o: o.get(0))

        k = 2
        while level:
            level = self.generateCandidateSizeK(level, k)
            k += 1

        self.writer.close()
        self.endTimeStamp = int(time.time() * 1000)

    def generateCandidateSizeK(self, levelK_1: List[Itemset], level: int) -> List[Itemset]:
        nextLevel: List[Itemset] = []

        i = 0
        while i < len(levelK_1):
            itemset1 = levelK_1[i]
            j = i + 1
            while j < len(levelK_1):
                itemset2 = levelK_1[j]

                go_loop1 = False
                go_loop2 = False

                for k in range(itemset1.size()):
                    if k == itemset1.size() - 1:
                        if itemset1.getItems()[k] >= itemset2.get(k):
                            go_loop1 = True
                            break
                    elif itemset1.getItems()[k] < itemset2.get(k):
                        go_loop2 = True
                        break
                    elif itemset1.getItems()[k] > itemset2.get(k):
                        go_loop1 = True
                        break

                if go_loop1:
                    break
                if go_loop2:
                    j += 1
                    continue

                inter = set()
                for val1 in itemset1.getTransactionsIds():
                    if val1 in itemset2.getTransactionsIds():
                        inter.add(val1)

                if len(inter) >= self.minSuppRelative:
                    newItemset = [0] * (itemset1.size() + 1)
                    newItemset[:itemset1.size()] = itemset1.itemset[:]
                    newItemset[itemset1.size()] = itemset2.getItems()[itemset2.size() - 1]
                    candidate = Itemset(newItemset)
                    candidate.setTIDs(inter)
                    nextLevel.append(candidate)

                j += 1
            i += 1

        if level > 2:
            for i in range(len(levelK_1)):
                for j in range(i + 1, len(levelK_1)):
                    candidate1 = levelK_1[i]
                    candidate2 = levelK_1[j]

                    skip_outer = False
                    for a in candidate1.getItems():
                        if candidate2.contains(a) is False:
                            b = None
                            for itemM in candidate2.getItems():
                                if candidate1.contains(itemM) is False:
                                    if b is not None:
                                        skip_outer = True
                                        break
                                    b = itemM
                            if skip_outer:
                                break
                            self.testIndirectRule(candidate1, a, b)
                    if skip_outer:
                        pass

        return nextLevel

    def testIndirectRule(self, itemset: Itemset, a: int, b: int):
        tidsA = self.mapItemTIDS.get(a, set())
        tidsB = self.mapItemTIDS.get(b, set())

        supportAB = 0
        for tidFromA in tidsA:
            if tidFromA in tidsB:
                supportAB += 1

        if supportAB < self.tsRelative:
            supAY = 0
            for tidA in tidsA:
                ok = True
                for item in itemset.getItems():
                    if (item != a) and (item != b):
                        if tidA not in self.mapItemTIDS.get(item, set()):
                            ok = False
                            break
                if ok:
                    supAY += 1

            confAY = supAY / float(len(tidsA))

            if confAY >= self.minconf:
                supBY = 0
                for tidB in tidsB:
                    ok = True
                    for item in itemset.getItems():
                        if (item != a) and (item != b):
                            if tidB not in self.mapItemTIDS.get(item, set()):
                                ok = False
                                break
                    if ok:
                        supBY += 1

                confBY = supBY / float(len(tidsB))
                if confBY >= self.minconf:
                    self.saveRule(a, b, itemset, confAY, confBY, supAY, supBY)

    def saveRule(self, a: int, b: int, itemset: Itemset, confAY: float, confBY: float, supAY: int, supBY: int):
        self.ruleCount += 1
        buffer = []
        buffer.append("(a= ")
        buffer.append(str(a))
        buffer.append(" b= ")
        buffer.append(str(b))
        buffer.append(" | mediator= ")
        for i in range(itemset.size()):
            if (itemset.get(i) != a) and (itemset.get(i) != b):
                buffer.append(str(itemset.get(i)))
                buffer.append(" ")
        buffer.append(") #sup(a,mediator)= ")
        buffer.append(str(supAY))
        buffer.append(" #sup(b,mediator)= ")
        buffer.append(str(supBY))
        buffer.append(" #conf(a,mediator)= ")
        buffer.append(str(confAY))
        buffer.append(" #conf(b,mediator)= ")
        buffer.append(str(confBY))
        self.writer.write("".join(buffer))
        self.writer.write("\n")

    def printStats(self):
        print("=============  INDIRECT RULES GENERATION - STATS =============")
        print(" Transactions count from database : " + str(self.tidcount))
        print(" Indirect rule count : " + str(self.ruleCount))
        print(" Total time ~ " + str(self.endTimeStamp - self.startTimestamp) + " ms")
        print("===================================================")


def main():
    script_dir = Path(__file__).resolve().parent
    input_path = script_dir / "contextIndirect.txt"
    output_path = script_dir / "output.txt"

    if not input_path.exists():
        print(f"Input file not found: {input_path.name}")
        print("Please place contextIndirect.txt in the same folder as this Python file.")
        return

    minsup = 0.6
    ts = 0.5
    minconf = 0.1

    indirect = AlgoINDIRECT()
    indirect.runAlgorithm(str(input_path), str(output_path), minsup, ts, minconf)
    indirect.printStats()

    print("\nOutput saved to:", output_path.name)
    print("\nContents of output file:\n")
    with open(output_path, "r", encoding="utf-8") as f:
        print(f.read(), end="")


if __name__ == "__main__":
    main()
