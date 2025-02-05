
"""Code for a simple terminal-based airing program that shows if rooms should be aired or not, based on the humidity
inside and outside (or in summer mode based on the temperature difference).
It can be run on a computer or a Raspberry Pi.
It needs at least one sensor (for humidity and temperature) outside and one sensor inside to work. In my case they
communicate over LAN/Wifi, and send the data in the format: 'temp, 2.87 78.36' """


import socket
import logging
from sty import fg, bg, ef, rs
from datetime import datetime


versionnr = "0.5"

roomlist = [["office", "192.168.178.35"], ["bathroom", "192.168.178.33"], ["living room", "192.168.178.32"], ["portable 36", "192.168.178.36"]]  # nested list in the format [[roomname, ip-address]]
outsidesensor = ["outside", "192.168.178.31"]
settings = {"portnr": 23,
            "displaylanguage": "en", # "en" for english (possible are "en" and "lu")
            "hum_threshold": 60,  # percentage of relative humidity which marks the limit up to which it's ok/not ok
            "mindiff": 0.1}  # 10 %  (has to be at least the tolerance of the humidity sensors (in this case +-2 percentage points))}

testerei = False  # for test mode
if testerei == True:
    logging.basicConfig(level = logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s', datefmt = "%Y-%m-%d %H:%M")


def calculate_abshumidity(currenttemp, currenthumidity):
    """calculates the absolute humidity out of relative temperature and humidity.
    Formula taken from: https://carnotcycle.wordpress.com/2012/08/04/how-to-convert-relative-humidity-to-absolute-humidity/"""
    ah = (6.112 * (2.71828**((17.67 * currenttemp) / (currenttemp + 243.5))) * currenthumidity * 2.1674) / (273.15 + currenttemp)
    return ah


def contact_sensor(ip_address, settingsdict):
    """responsible for the communication with the sensor."""
    socket_on = False
    # create a socket / connection to the sensor:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)  # set own timeout
        # pass the IP-address that should be called to the connect-method:
        s.connect((ip_address, settingsdict["portnr"]))
        socket_on = True
    except TimeoutError:
        #logging.exception("timed out")
        return "timeouterror"
    except OSError:
        #logging.exception("problem with communication")
        return "Verbindungsproblem" if settingsdict["displaylanguage"] == "lu" else "communication problem"
    except:  # for the case there were another error than OSError
        #logging.exception("allgemengen Problem!")
        return "Verbindungsproblem - allg. except agespr.!!"

    if socket_on == True:  # checks if the socket exists/was created
        s.send("temp.".encode())
        try:
            s.settimeout(5)  # 10
            answer = s.recv(1024)
        except (TimeoutError, socket.timeout):
            return "Timeout"
        except:  # for the case there were another error than TimeoutError
            return "allgem. except agesprongen bei Message-Auswertung!!"
        finally: # close the socket (this block runs even if there is a return in the except-blocks above)
            s.close()

        answer = answer.decode()

        return answer


def process_sensordata(sensorlist, settingsdict):
    """There are a few sensors (for different rooms and outside). The function requests the data from the sensors and
    checks if it's worth to air one or more rooms (if the air outside is dryer than inside, or for the summer-mode:
    cooler than the inside), based on temperature and humidity inside and outside.
    The answer of a sensor comes in the format: 'temp, 2.87 78.36' (if there is no error message).

    Returns the outside values, a list with the error-messages and a dictionary with different values and evaluations,
    to be able to print it accordingly."""

    datadict = {}  # in the format {"roomname": {"temp": , "hum": , ...}}
    outsidedict = {}
    errorlist = []  # error messages, if the communication with the sensors failed

    communication_port = settingsdict["portnr"]
    displaylanguage = settingsdict["displaylanguage"]
    mindiff = settingsdict["mindiff"]

    # COLLECT SENSOR DATA:
    # first get outside sensor data to be able to compare:
    outsidedata = contact_sensor(outsidesensor[1], settingsdict)  # IP and settings
    if outsidedata.startswith("temp"):
        split_outsidevalues = outsidedata.split()  # ['temp,', '0.91', '79.51']
        outdoor_temp = float(split_outsidevalues[1])
        outdoor_hum = float(split_outsidevalues[2])
        outdoor_abshum = (round(calculate_abshumidity(outdoor_temp, outdoor_hum), 2))
        outsidedict[outsidesensor[0]] = {}
        outsidedict["temp"] = outdoor_temp
        outsidedict["hum"] = outdoor_hum
        outsidedict["abshum"] = outdoor_abshum
        logging.debug(f"outdoor_abshum: {outdoor_abshum}")
        logging.debug(f"outdoor_temp: {outdoor_temp}")
        logging.debug(f"outdoor_hum: {outdoor_hum}")
    else:  # error message
        if displaylanguage == "lu":
            errorlist.append(f"{outsidesensor[0]}: FEHLER beim Sensor '{outsidesensor[0]}'. Äntwert as: '{outsidedata}'")
        else:  # displaylanguage is english
            errorlist.append(f"{outsidesensor[0]}: PROBLEM with sensor '{outsidesensor[0]}'. Answer is: '{outsidedata}'")

    # get data from the room sensors and create a dictionary with the data for the different rooms:
    if len(outsidedict) != 0:  # if there is no outside data, comparisons are impossible
        for singlelist in sensorlist:
            currentroomdata = contact_sensor(singlelist[1], settingsdict)  # IP and settings
            singleroomname = singlelist[0]
            if currentroomdata.startswith("temp"):
                split_roomvalues = currentroomdata.split()  # ['temp,', '0.91', '79.51']
                temp = float(split_roomvalues[1])
                hum = float(split_roomvalues[2])
                abshum = round(calculate_abshumidity(temp, hum), 2)
                tempdiff = round(temp - outdoor_temp, 2)
                abshumdiff = round(abshum - outdoor_abshum, 2)
                datadict[singleroomname] = {}
                datadict[singleroomname]["temp"] = temp
                datadict[singleroomname]["hum"] = hum
                datadict[singleroomname]["abshum"] = abshum

                # EVALUATE SENSOR DATA and write the evaluation results to the dictionary (calculate absolute humidity
                #   for the different places/sensors and decide whether it needs airing or not):
                if hum >= settingsdict["hum_threshold"]:
                    if abshumdiff > 0 and (abshumdiff > (abshum * mindiff)):
                        need_to_air = "leften"
                    else:
                        need_to_air = "bausse mei fiicht"
                else:
                    need_to_air = "brauch net leften"
                datadict[singleroomname]["hum_ok"] = hum <= 60
                datadict[singleroomname]["need_to_air"] = need_to_air
                datadict[singleroomname]["cooler_outside"] = tempdiff > 0 and (tempdiff > temp * mindiff)
                datadict[singleroomname]["abshumdiff"] = abshumdiff
                datadict[singleroomname]["tempdiff"] = tempdiff

            else:  # if sensor data is not in the right format / it returns an error message
                if displaylanguage == "lu":
                    errorlist.append(f"{singleroomname}: FEHLER beim Sensor '{singleroomname}'. Äntwert as: '{currentroomdata}'")
                else:  # displaylanguage is english
                    errorlist.append(f"{singleroomname}: PROBLEM with sensor '{singleroomname}'. Answer is: '{currentroomdata}'")

    logging.debug(f"sensordata: {datadict}\nerrordata: {errorlist}")

    if len(datadict) == 0:
        errormessage = "Keng Werter vun Sensoren do, keng Angab méiglech!" if displaylanguage == "lu" else "No sensor data available, evaluation not possible!"
        errorlist.append(errormessage)  # (colour this message red?)

    if len(outsidedict) == 0:
        errormessageoutside = "Keng Werter vum Bausse-Sensor do - Keng Vergläicher méiglech!" if displaylanguage == "lu" else "No data available from outside-sensor, comparison not possible"
        errorlist.append(errormessageoutside)  # (colour this message red?)

    logging.debug(f"resultsdict (datadict): {datadict}")
    logging.debug(f"errorlist: {errorlist}")

    return outsidedict, datadict, errorlist


def create_output(sensorlist, settingsdict, summer = False):
    """arranges the data for outputting in the terminal – creates the output (prints the strings
    in the desired way), with colours to better spot the results on which the user should take action.
    The name of the room is marked in green, red or orange (is ok / should be aired / can't be aired because it's too
    humid outside). The relative humidity of the room is marked in green (humidity under threshold) or red (above
    threshold), regardless of the airing recommendation.
    The recommendations for the summer mode are blue (if it's cooler outside and should be aired), or orange if the
    windows should stayed closed because of the heat.
    (colours, effects etc, of the sty module, see: https://sty.mewo.dev/index.html)"""

    outsidedict, datadict, errorlist = process_sensordata(sensorlist, settingsdict)
    currenttime = datetime.now().strftime("%H:%M")

    displaylanguage = settingsdict["displaylanguage"]

    outputsrings = []
    summeroutputstrings = []
    morehumidoutside = None

    if len(errorlist) != 0:
        print(fg(217) + "(" + currenttime + ")" + fg.rs)
        for singleproblem in errorlist:
            print(fg(217) + singleproblem + fg.rs)  # 217 is pale pink

    # if there is sensor data in the dictionary and "outside" is not missing:
    if len(datadict) != 0 and len(outsidedict) != 0:
        # singleroomname, temp, hum, abshum, hum <= 60, need_to_air, tempdiff > 0 and (tempdiff > temp * mindiff), abshumdiff, tempdiff
        for singleroom in datadict:
            abshumdiff = datadict[singleroom]["abshumdiff"]
            tempdiff = datadict[singleroom]["tempdiff"]
            roomname = singleroom

            # colour the room name and instruction:
            if datadict[singleroom]["need_to_air"] == "leften":  # (need to air)
                roomname = fg.li_red + roomname + fg.rs  # red
                # choosing the language for the output word:
                lefterei = fg.li_red + "leften" + fg.rs if displaylanguage == "lu" else fg.li_red + "ventilate" + fg.rs
            elif datadict[singleroom]["need_to_air"] == "brauch net leften":  # (no need to air)
                roomname = fg.li_green + roomname + fg.rs
                lefterei = fg.li_green + "brauch net leften" + fg.rs if displaylanguage == "lu" else fg.li_green + "no need to air" + fg.rs
            elif datadict[singleroom]["need_to_air"] == "bausse mei fiicht":  # (more humidity outside)
                roomname = fg(208) + roomname + fg.rs  # orange
                lefterei = fg(208) + "bausse méi fiicht! *" + fg.rs if displaylanguage == "lu" else fg(208) + "more humid outside!*" + fg.rs
                morehumidoutside = True

            # colour the relative humidity:
            if datadict[singleroom]["hum_ok"] == True:
                relhum = fg.li_green + str(round(datadict[singleroom]["hum"], 1)) + " %" + fg.rs
            else:
                relhum = fg.li_red + str(round(datadict[singleroom]["hum"], 1)) + " %" + fg.rs

            if displaylanguage == "lu":
                outputsrings.append(f"{roomname}: {round(datadict[singleroom]['temp'], 1)} °C, {relhum}, abshum: {datadict[singleroom]['abshum']}, abshumdiff zu baussen: {abshumdiff} - {lefterei} -")  # %-symbol already included in relhum because of colouring
            else:
                outputsrings.append(f"{roomname}: {round(datadict[singleroom]['temp'], 1)} °C, {relhum}, abshum: {datadict[singleroom]['abshum']}, abshumdiff to outside: {abshumdiff} - {lefterei} -")

            if summer == True:
                # todo: also include a minimum (temperature) difference in the summer mode?
                if datadict[singleroom]['cooler_outside'] == True:  # (should air)
                    roomname = fg.li_blue + singleroom + fg.rs
                    lefterei = fg.li_blue + "leften" + fg.rs if displaylanguage == "lu" else fg.li_blue + "ventilate" + fg.rs
                else:  # (outside warmer)
                    roomname = fg(208) + singleroom + fg.rs  # orange
                    lefterei = fg(208) + "bausse méi warm" + fg.rs  if displaylanguage == "lu" else "warmer outside"
                if displaylanguage == "lu":
                    summerstr = f"{roomname}: {datadict[singleroom]['temp']} °C, tempdiff zu baussen: {tempdiff} - {lefterei} -"
                else:
                    summerstr = f"{roomname}: {datadict[singleroom]['temp']} °C, tempdiff to outside: {tempdiff} - {lefterei} -"
                summeroutputstrings.append(summerstr)
                #logging.debug(summerstr)

        if displaylanguage == "lu":
            print("\n" + ef.u + "FIICHTEGKEET" + ef.rs + " (" + currenttime +")")  # (humidity), underlined
            print(f"outside: temp: {round(outsidedict['temp'], 1)} °C, relhum: {round(outsidedict['hum'], 1)} %, abshum: {outsidedict['abshum']} g/m3")
        else: # english
            print("\n" + ef.u + "HUMIDITY" + ef.rs + " (" + currenttime +")")
            print(f"outside: temp: {round(outsidedict['temp'], 1)} °C, relhum: {round(outsidedict['hum'], 1)} %, abshum: {outsidedict['abshum']} g/m3")

        for singlestr in outputsrings:
            print(singlestr)
        if morehumidoutside == True:
            notestr = "(méi fiicht resp. Differenz < 10%)" if displaylanguage == "lu" else "(more humid or difference < 10%)"
            print(fg(208) + " * " + fg.rs + notestr)

        if summer == True:
            print("\n" + ef.u + "SUMMER" + ef.rs+ " (" + currenttime +")")  # underlined
            for singlesummerstr in summeroutputstrings:
                print(singlesummerstr)

# --------------------------------

# start the program:

while True:

    if settings["displaylanguage"] == "lu":
        user_advice = "'r' fier refresh/uweisen, 's' fier summerversioun, 'e' fier exit: "
    else:  # english
        user_advice = "'r' for refresh/display, 's' for summer mode, 'e' for exit: "
    # print line of dashes:
    print("\n\n" + '-' * (len(user_advice) - 1))  # -1 because of the space on the end

    inputcommand = input(user_advice)

    if inputcommand.lower() == "e":
        break
    elif inputcommand.lower() == "r":
        create_output(roomlist, settings)
    elif inputcommand.lower() == "s":
        create_output(roomlist, settings, summer = True)  # summer mode compares temperature to be able to cool down the rooms


