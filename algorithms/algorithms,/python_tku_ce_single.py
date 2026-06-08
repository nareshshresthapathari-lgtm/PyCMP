import os
import time
import random


class MemoryLogger:
    _instance = None

    def __init__(self):
        self.maxMemory = 0.0

    @classmethod
    def getInstance(cls):
        if cls._instance is None:
            cls._instance = MemoryLogger()
        return cls._instance

    def getMaxMemory(self):
        return self.maxMemory

    def reset(self):
        self.maxMemory = 0.0

    def checkMemory(self):
        # Approximation for Python.
        # Java version uses: (totalMemory - freeMemory) / 1024d / 1024d
        # This output stat is not used in the itemset file itself.
        try:
            import psutil
            process = psutil.Process(os.getpid())
            currentMemory = process.memory_info().rss / 1024.0 / 1024.0
        except Exception:
            currentMemory = 0.0

        if currentMemory > self.maxMemory:
            self.maxMemory = currentMemory
        return currentMemory


class Pair:
    def __init__(self):
        self.item = 0
        self.utility = 0


class HUI:
    def __init__(self, itemset, fitness):
        self.itemset = itemset
        self.fitness = fitness


class Item:
    def __init__(self, item, transactionCount):
        self.item = item
        self.TIDS = set()


class Particle:
    def __init__(self, length=0):
        self.X = set()   # simulate Java BitSet with set of indices
        self.fitness = 0
        self.length = length

    def copyParticle(self, particle1):
        self.X = set(particle1.X)
        self.fitness = particle1.fitness

    def calculateFitness(self, k, templist, database, twuPattern):
        if k == 0:
            return

        fitness = 0
        for m in range(len(templist)):
            p = templist[m]
            i = 0
            q = 0
            temp = 0
            total_sum = 0

            while q < len(database[p]) and i < len(twuPattern):
                if i in self.X:
                    if database[p][q].item == twuPattern[i]:
                        total_sum += database[p][q].utility
                        i += 1
                        q += 1
                        temp += 1
                    else:
                        q += 1
                else:
                    i += 1

            if temp == k:
                fitness += total_sum

        self.fitness = fitness


class AlgoTKUCE:
    def __init__(self):
        self.maxMemory = 0.0
        self.startTimestamp = 0
        self.endTimestamp = 0
        self.pop_size = 2000
        self.iterations = 2000
        self.transactionCount = 0
        self.K = 0
        self.minUtility = 0
        self.alpha = 0.2

        self.mapItemToTWU = {}
        self.twuPattern = []
        self.p = []

        self.population = []
        self.huiSets = []
        self.database = []
        self.Items = []
        self.huiTopKBA = []

    def runAlgorithm(self, input_file, output_file, k):
        self.K = k
        MemoryLogger.getInstance().reset()
        self.startTimestamp = int(time.time() * 1000)

        self.mapItemToTWU = {}
        self.population = []
        self.huiSets = []
        self.database = []
        self.Items = []
        self.huiTopKBA = []
        self.transactionCount = 0
        self.minUtility = 0

        # First scan: TWU
        with open(input_file, "r", encoding="utf-8") as myInput:
            for thisLine in myInput:
                thisLine = thisLine.strip()
                if thisLine == "" or thisLine[0] in "#%@":
                    continue

                self.transactionCount += 1
                split = thisLine.split(":")
                items = split[0].split(" ")
                transactionUtility = int(split[1])

                for i in range(len(items)):
                    item = int(items[i])
                    twu = self.mapItemToTWU.get(item)
                    twu = transactionUtility if twu is None else twu + transactionUtility
                    self.mapItemToTWU[item] = twu

        # Second scan: build database
        with open(input_file, "r", encoding="utf-8") as myInput:
            for thisLine in myInput:
                thisLine = thisLine.strip()
                if thisLine == "" or thisLine[0] in "#%@":
                    continue

                split = thisLine.split(":")
                items = split[0].split(" ")
                utilityValues = split[2].split(" ")

                revisedTransaction = []
                for i in range(len(items)):
                    pair = Pair()
                    pair.item = int(items[i])
                    pair.utility = int(utilityValues[i])

                    if self.mapItemToTWU[pair.item] >= self.minUtility:
                        revisedTransaction.append(pair)

                self.database.append(revisedTransaction)

        self.twuPattern = list(self.mapItemToTWU.keys())
        self.twuPattern.sort()
        self.p = [0.0] * len(self.twuPattern)
        self.Items = [Item(item, self.transactionCount) for item in self.twuPattern]

        # Build TIDS bitsets
        for i in range(len(self.database)):
            for j in range(len(self.Items)):
                for m in range(len(self.database[i])):
                    if self.Items[j].item == self.database[i][m].item:
                        self.Items[j].TIDS.add(i)

        MemoryLogger.getInstance().checkMemory()

        if len(self.twuPattern) > 0:
            self.generatePop()

            for _ in range(2000):
                self.population.sort(key=lambda p: p.fitness, reverse=True)
                diff = self.population[0].fitness - self.population[1999].fitness
                if diff == 0:
                    break
                self.update()

            for i in range(self.K):
                if i <= len(self.huiTopKBA) - 1:
                    self.insert(self.huiTopKBA[i])

            var36 = self.K
            while var36 < len(self.huiTopKBA) and \
                  self.huiTopKBA[var36].fitness == self.huiTopKBA[var36 - 1].fitness:
                self.insert(self.huiTopKBA[var36])
                var36 += 1

        self.writeOut(output_file)
        MemoryLogger.getInstance().checkMemory()
        self.maxMemory = MemoryLogger.getInstance().getMaxMemory()
        self.endTimestamp = int(time.time() * 1000)

    def generatePop(self):
        for i in range(2000):
            tempParticle = Particle(len(self.twuPattern))
            j = 0
            k = int(random.random() * len(self.twuPattern))

            while j < k:
                # Exact Java source behavior:
                # temp = (int)(Math.random() * twuPattern.size()) + 1;
                temp = int(random.random() * len(self.twuPattern)) + 1
                if temp not in tempParticle.X:
                    j += 1
                    tempParticle.X.add(temp)

            transList = []
            self.isRBAIndividual(tempParticle, transList)
            tempParticle.calculateFitness(k, transList, self.database, self.twuPattern)
            self.population.insert(i, tempParticle)
            self.insertTopList(self.population[i])

    def update(self):
        num = [0] * len(self.twuPattern)

        for i in range(400):
            for j in range(len(self.twuPattern)):
                if j in self.population[i].X:
                    num[j] += 1

        self.minUtility = self.population[399].fitness

        for i in range(len(self.twuPattern)):
            self.p[i] = float(num[i] / 400.0)

        k = 0
        for i in range(2000):
            tempParticle = Particle(len(self.twuPattern))
            self.update_Particle(tempParticle)

            transList = []
            self.isRBAIndividual(tempParticle, transList)
            k = len(tempParticle.X)
            tempParticle.calculateFitness(k, transList, self.database, self.twuPattern)

            self.population.insert(i, tempParticle)
            self.insertTopList(self.population[i])

        # IMPORTANT:
        # Java does NOT trim population here.
        # So do not trim.

    def update_Particle(self, temp):
        for i in range(len(self.twuPattern)):
            if random.random() < self.p[i]:
                temp.X.add(i)

    def insertTopList(self, tmp):
        temp = Particle(len(self.twuPattern))
        temp.copyParticle(tmp)

        if len(self.huiTopKBA) == 0:
            self.huiTopKBA.append(temp)
            return

        max_idx = 0
        min_idx = self.K - 1
        mid = 0

        if len(self.huiTopKBA) < self.K:
            min_idx = len(self.huiTopKBA) - 1
            if temp.fitness < self.huiTopKBA[min_idx].fitness:
                self.huiTopKBA.append(temp)
                return
        else:
            if temp.fitness < self.huiTopKBA[min_idx].fitness:
                return

        while max_idx <= min_idx:
            mid = (max_idx + min_idx) // 2
            if temp.fitness > self.huiTopKBA[mid].fitness:
                min_idx = mid - 1
            elif temp.fitness < self.huiTopKBA[mid].fitness:
                max_idx = mid + 1
            else:
                return

        if temp.fitness >= self.huiTopKBA[mid].fitness:
            self.huiTopKBA.insert(mid, temp)
        else:
            self.huiTopKBA.insert(mid + 1, temp)

    def isRBAIndividual(self, tempBAIndividual, out_list):
        templist = []
        for i in range(len(self.twuPattern)):
            if i in tempBAIndividual.X:
                templist.append(i)

        if len(templist) == 0:
            return False

        tempBitSet = set(self.Items[templist[0]].TIDS)
        midBitSet = set(tempBitSet)

        for i in range(1, len(templist)):
            tempBitSet = tempBitSet.intersection(self.Items[templist[i]].TIDS)
            if len(tempBitSet) != 0:
                midBitSet = set(tempBitSet)
            else:
                tempBitSet = set(midBitSet)
                tempBAIndividual.X.discard(templist[i])

        if len(tempBitSet) == 0:
            return False
        else:
            for m in range(max(tempBitSet) + 1 if tempBitSet else 0):
                if m in tempBitSet:
                    out_list.append(m)
            return True

    def insert(self, tempParticle):
        temp = []
        for i in range(len(self.twuPattern)):
            if i in tempParticle.X:
                temp.append(str(self.twuPattern[i]))
                temp.append(" ")

        itemset_str = "".join(temp)

        if len(self.huiSets) == 0:
            self.huiSets.append(HUI(itemset_str, tempParticle.fitness))
        else:
            i = 0
            while i < len(self.huiSets) and itemset_str != self.huiSets[i].itemset:
                i += 1
            if i == len(self.huiSets):
                self.huiSets.append(HUI(itemset_str, tempParticle.fitness))

    def writeOut(self, output_file):
        with open(output_file, "w", encoding="utf-8") as writer:
            for i in range(len(self.huiSets)):
                line = f"{self.huiSets[i].itemset}#UTIL:{self.huiSets[i].fitness}"
                writer.write(line + "\n")

    def printStats(self):
        print("============= TKU-CE Algorithm v 2.52 ==========")
        print(f" Total time ~ {self.endTimestamp - self.startTimestamp} ms")
        print(f" Memory ~ {self.maxMemory} MB")
        print(f" High-utility itemsets count : {len(self.huiSets)}")
        print("================================================")


if __name__ == "__main__":
    algo = AlgoTKUCE()
    algo.runAlgorithm("DB_Utility.txt", "#104_output.txt", 7)
    algo.printStats()