import subprocess
import sys
import re
import time
import os.path
import datetime
import xml.dom.minidom
from xml.dom.minidom import parse

#
#
#

# Parse simple xml that is produced for one test case run
def FindTestCaseNodeXml(xmlPath, testSuiteName, testCaseName):
  try:
    tree = xml.dom.minidom.parse(xmlPath)
    testsuites = tree.documentElement.getElementsByTagName("testsuite")
    for testsuite in testsuites:
      if (testsuite.hasAttribute("name")) and (testsuite.getAttribute("name") == testSuiteName):
        testcases = testsuite.getElementsByTagName("testcase")
        for testcase in testcases:
          if (testcase.hasAttribute("name")) and (testcase.getAttribute("name") == testCaseName):
            return testcase
  except Exception:
    print "WARNING: failed to parse xml for test " + testSuiteName + "." + testCaseName + " (" + xmlPath + ")"
    return None
  return None

#
#
#

# Get list of test cases
# Run test app with --gtest_list_tests flag to get list of tests in app as captured output
# Output contains a raw output of application, which contains list of tests and other stuff
# Parsing rules:
# stuff stuff stuff ...
# TestGroup1.
#   TestCase1
#   TestCase2
# TestGroup2.
#   TestCase1
#   TestCase2
# stuff stuff stuff ...
# As we can see TestGroup starts with char and ends with dot, and next line is TestCase which starts with spaces, name starts with char
# WARNING! It is unreliable method to get list of test cases because app can output any stuff which can be interpreted as test suite/case
def GetListOfTestCases(appPath, commandLineArgs):
  cmdLine = [appPath, "--gtest_list_tests"]

  for param in commandLineArgs:
    if (param.startswith("--gtest_filter=")):
      cmdLine.append(param)

  output = []
  code = subprocess.Popen(cmdLine, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  for line in code.stdout:
    output.append(line.rstrip())
  testCases = []
  lastOneTestGroup = None
  for line in output:
    matchTestGroup = re.match(r'^([A-Za-z0-9_]*)\.$', line, re.M|re.I)
    if (matchTestGroup):
      lastOneTestGroup = matchTestGroup.group()[:-1]
    elif (lastOneTestGroup):
      matchTestCase = re.match(r'^(\s*)([A-Za-z0-9_]*)$', line, re.M|re.I)
      if (matchTestCase):
        testCases.append({'TestSuiteName':lastOneTestGroup, 'TestCaseName':matchTestCase.group().lstrip()})
      else:
        lastOneTestGroup = None
  return testCases

#
#
#

# Round time
def RountTime(val):
  val = val * 1000.0
  val = int(val + 0.5)
  val = float(val) / 1000.0
  return val

# Removes file
def RemoveFile(path):
  try:
    if (os.path.isfile(path)):
      os.remove(path)
  except Exception:
    print "WARNING: failed to remove " + path

# Renames file
def RenameFile(src, dst):
  try:
    if (os.path.isfile(dst)):
      os.remove(dst)
    os.rename(src, dst)
  except Exception:
    print "WARNING: failed to rename " + src + " to " + dst

#
#
#

# Execute test cases
# Run separate process for each test case
def ExecuteTestCases(appPath, commandLineArgs, testCases):
  startTime = time.time()
  timestamp = datetime.datetime.fromtimestamp(startTime).strftime('%Y-%m-%dT%H:%M:%S')
  alsoRunDisabledTests = False
  outputXmlPath = None
  testSuitesResults = {}
  countPassed = 0
  countFailed = 0
  countSkipped = 0
  exitCode = 0

  for param in commandLineArgs:
    if (param == "--gtest_also_run_disabled_test"):
      alsoRunDisabledTests = True
    elif (param.startswith("--gtest_output=xml:")):
      outputXmlPath = param[len("--gtest_output=xml:"):]

  for testCase in testCases:
    testCaseXml = None
    testCaseTime = 0.0
    testCaseRunned = False
    testCaseExitCode = 0
    testCaseFailed = 0
    testCaseSkipped = 0
    testCasePassed = 0
    testCaseStartTime = float(time.time())

    if (outputXmlPath):
      RemoveFile(outputXmlPath)

    if ((not testCase['TestCaseName'].startswith("DISABLED_")) or alsoRunDisabledTests):
      cmdLine = [appPath]
      cmdLine.extend(commandLineArgs)
      cmdLine.append("--gtest_filter=" + testCase['TestSuiteName'] + "." + testCase['TestCaseName'])
      testCaseRunned = True
      testCaseExitCode = subprocess.call(cmdLine)
      if (testCaseExitCode != 0):
        exitCode = testCaseExitCode
        testCaseFailed = 1
      else:
        testCasePassed = 1

      if (outputXmlPath):
        testCaseNode = FindTestCaseNodeXml(outputXmlPath, testCase['TestSuiteName'], testCase['TestCaseName'])

        if (testCaseNode):
          testCaseTime = float(testCaseNode.getAttribute("time"))
          testCaseXml = testCaseNode.toxml()
        else:
          testCaseTime = RountTime(float(time.time()) - testCaseStartTime)
          testCaseXml = '<testcase name="' + testCase['TestCaseName'] + '" status="noxml" time="' + str(testCaseTime) + '" classname="' + testCase['TestSuiteName'] + '" />'

        RenameFile(outputXmlPath, outputXmlPath + "." + testCase['TestSuiteName'] + "." + testCase['TestCaseName'] + ".xml")

      else:
        testCaseTime = RountTime(float(time.time()) - testCaseStartTime)

    else:
      testCaseSkipped = 1

      if (outputXmlPath):
        testCaseXml = '<testcase name="' + testCase['TestCaseName'] + '" status="notrun" time="0" classname="' + testCase['TestSuiteName'] + '" />'

    testCaseResult = {'TestSuiteName':testCase['TestSuiteName'], 'TestCaseName':testCase['TestCaseName'], 'Runned':testCaseRunned, 'ExitCode':testCaseExitCode, 'Time':testCaseTime, 'Xml':testCaseXml}

    if (not testSuitesResults.has_key(testCase['TestSuiteName'])):
      testSuitesResults[testCase['TestSuiteName']] = {'Time':0.0, 'Passed':0, 'Failed':0, 'Skipped':0, 'Count':0, 'TestCasesResults':[]}
    testSuiteResult = testSuitesResults[testCase['TestSuiteName']]
    testSuiteResult['Time'] += testCaseTime
    testSuiteResult['Count'] += 1
    testSuiteResult['Skipped'] += testCaseSkipped
    testSuiteResult['Passed'] += testCasePassed
    testSuiteResult['Failed'] += testCaseFailed
    testSuiteResult['TestCasesResults'].append(testCaseResult)

    countPassed += testCasePassed
    countFailed += testCaseFailed
    countSkipped += testCaseSkipped

  totalTime = RountTime(float(time.time()) - startTime)

  return {'TestSuitesResults':testSuitesResults, 'Tests':len(testCases), 'Passed':countPassed, 'Failed':countFailed, 'Skipped':countSkipped, 'Time':totalTime, 'ExitCode':exitCode, 'Timestamp':timestamp, 'Name':'AllTests'}

#
#
#

# Output plain text report in stdout
def PrintPlainTextReport(result):
  print "---------------------------------------------------------------------------"
  print "Name:"+result['Name']+", Timestamp:"+result['Timestamp']
  print "---------------------------------------------------------------------------"
  testSuitesResults = result['TestSuitesResults']
  for testSuiteName in testSuitesResults.keys():
    testSuiteResult = testSuitesResults[testSuiteName]
    print testSuiteName + " (Tests:"+str(testSuiteResult['Count'])+", Passed:"+str(testSuiteResult['Passed'])+", Failed:"+str(testSuiteResult['Failed'])+", Disabled:"+str(testSuiteResult['Skipped'])+", Time:"+str(testSuiteResult['Time'])+")"
    for testCaseResult in testSuiteResult['TestCasesResults']:
      if (testCaseResult['Runned'] == False):
        print "  [DISABLED] "+testCaseResult['TestCaseName']
      elif (testCaseResult['ExitCode'] == 0):
        print "    [PASSED] "+testCaseResult['TestCaseName']+" (Time:"+str(testCaseResult['Time'])+")"
      else:
        print "    [FAILED] "+testCaseResult['TestCaseName']+" (ExitCode:"+str(testCaseResult['ExitCode'])+", Time:"+str(testCaseResult['Time'])+")"
  print "---------------------------------------------------------------------------"
  print "Tests:"+str(result['Tests'])+ ", Passed:"+str(result['Passed'])+", Failed:"+str(result['Failed'])+", Disabled:"+str(result['Skipped'])+", Time:"+str(result['Time'])
  print "---------------------------------------------------------------------------"

#
#
#

# Output report as gtest xml
def PrintGtestXmlReport(result, filePath):
  f = None
  try:
    f = open(filePath, "w")
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
    testSuitesResults = result['TestSuitesResults']
    f.write('<testsuites tests="'+str(result['Tests'])+'" failures="'+str(result['Failed'])+'" disabled="'+str(result['Skipped'])+'" errors="0" timestamp="'+result['Timestamp']+'" time="'+str(result['Time'])+'" name="'+result['Name']+'">\n')
    for testSuiteName in testSuitesResults.keys():
      testSuiteResult = testSuitesResults[testSuiteName]
      f.write(' <testsuite name="'+testSuiteName+'" tests="'+str(testSuiteResult['Count'])+'" failures="'+str(testSuiteResult['Failed'])+'" disabled="'+str(testSuiteResult['Skipped'])+'" errors="0" time="'+str(testSuiteResult['Time'])+'">\n')
      for testCaseResult in testSuiteResult['TestCasesResults']:
        f.write('  '+testCaseResult['Xml']+'\n')
      f.write(' </testsuite>\n')
    f.write('</testsuites>\n')
  except:
    print "WARNING: failed to write XML (" + filePath + ")"
  if (f):
    f.close()

#
#
#

if (len(sys.argv) < 2):
  print "ERROR: specify path to the google test application"
  exit(-1)

testApplicationPath = sys.argv[1]

if (not os.path.isfile(testApplicationPath)):
  print "ERROR: specify VALID path to the google test application ("+testApplicationPath+" is not a file)"
  exit(-1)

testApplicationCmdLine = []
outputXmlPath = None
for cmdLineParam in sys.argv[2:]:
  testApplicationCmdLine.append(cmdLineParam)
  if (cmdLineParam.startswith("--gtest_output=xml:")):
    outputXmlPath = cmdLineParam[len("--gtest_output=xml:"):]
  elif (cmdLineParam.startswith("--gtest_output=")):
    print "ERROR: only XML output supported"
    exit(-1)

testCases = GetListOfTestCases(testApplicationPath, testApplicationCmdLine)

result = ExecuteTestCases(testApplicationPath, testApplicationCmdLine, testCases)

PrintPlainTextReport(result)

if (outputXmlPath):
  PrintGtestXmlReport(result, outputXmlPath)

sys.exit(result['ExitCode'])
