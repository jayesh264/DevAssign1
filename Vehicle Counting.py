import sys
import cv2
from trackers.tracker import create_blob, add_new_blobs, remove_duplicates
import numpy as np
from collections import OrderedDict
from detectors.detector import get_bounding_boxes
import uuid
import os
import contextlib
from datetime import datetime
import argparse
from utils.detection_roi import get_roi_frame, draw_roi
from counter import get_counting_line, is_passed_counting_line
from selectroi import selectroi
import time
from detectors.yolo.classifier import load_labels
import pandas as pd

class VehicleCounter():

    def __init__(self, initial_frame, detector, tracker, droi, show_droi, mcdf, mctf, di, cl_position, framerate):
        self.frame = initial_frame # current frame of video
        self.detector = detector
        self.tracker = tracker
        self.droi =  droi # detection region of interest
        self.show_droi = show_droi
        self.mcdf = mcdf # maximum consecutive detection failures
        self.mctf = mctf # maximum consecutive tracking failures
        self.di = di # detection interval
        self.cl_position = line if args.clposition == None else cl_position # counting line position

        self.frameno = 1
        self.labels = []
        self.count_list = {"label":[], "model":[], "luxury":[], "time":[]}
        self.framerate = 30 if framerate == None else framerate
        self.blobs = OrderedDict()
        self.blob_id = 1
        self.blob_label = "NA"
        self.f_height, self.f_width, _ = self.frame.shape
        self.frame_count = 0 # number of frames since last detection
        self.vehicle_count = 0 # number of vehicles counted
        self.counting_line = get_counting_line(self.cl_position, self.f_width, self.f_height) if cl_position == None else get_counting_line(self.cl_position, self.f_width, self.f_height)
        self.direction = 0 if args.direction == None else 1
        self.label_luxury = load_labels('luxury.txt')
        self.label_nonluxury = load_labels('non-luxury.txt')

        # create blobs from initial frame
        droi_frame = get_roi_frame(self.frame, self.droi)
        initial_boxes,labels = get_bounding_boxes(droi_frame, self.detector)
        self.labels = labels
        for i, box in enumerate(initial_boxes):
            _blob = create_blob(box, frame, self.tracker)
            self.blobs[self.blob_id] = (_blob, labels[i])
            # self.blobs[self.blob_label] = _label
            self.blob_id += 1


    def get_count(self):
        return self.vehicle_count

    def get_blobs(self):
        return self.blobs

    def count(self, frame):
        log = []
        self.frame = frame

        for _id, (blob, _label) in list(self.blobs.items()):
            # update trackers
            success, box = blob.tracker.update(self.frame)
            if success:
                blob.num_consecutive_tracking_failures = 0
                blob.update(box)
            else:
                blob.num_consecutive_tracking_failures += 1

            # count vehicles that have left the frame if no counting line exists
            # or those that have passed the counting line if one exists
            if (self.counting_line == None and \
                    (blob.num_consecutive_tracking_failures == self.mctf or blob.num_consecutive_detection_failures == mcdf) and \
                    not blob.counted) \
                        or \
                    (self.counting_line != None and \
                    is_passed_counting_line(blob.centroid, self.counting_line, self.cl_position, self.direction) and \
                    not blob.counted):
                blob.counted = True
                self.vehicle_count += 1
                # if _label in self.count_list:
                # 	self.count_list['label'].append(_label) 
                # else:
                # 	self.count_list[_label] = 1
                if _label[:3] == "car":
                    self.count_list['label'].append(_label[:3])
                    self.count_list['model'].append(_label[3:])
                    if _label[3:] in self.label_luxury:
                        self.count_list['luxury'].append("1")
                    else:
                        self.count_list['luxury'].append("0")
                    self.count_list['time'].append(round(self.frameno/self.framerate, 2))                        
                    
                else:
                    self.count_list['label'].append(_label)
                    self.count_list['model'].append("NA")
                    self.count_list['luxury'].append("NA")
                    self.count_list['time'].append(round(self.frameno/self.framerate, 2))
                 
                
                log.append({'blob_id': _id, 'count': self.vehicle_count, 'datetime': datetime.now()})

            if blob.num_consecutive_tracking_failures >= self.mctf:    
                # delete untracked blobs
                del self.blobs[_id]

        if self.frame_count >= self.di:
            # rerun detection
            droi_frame = get_roi_frame(self.frame, self.droi)
            boxes, labels= get_bounding_boxes(droi_frame, self.detector)
            self.labels = labels
            # for i, (x,y,w,h) in enumerate(boxes):      
            #     cv2.rectangle(self.frame, (x, y), (x + w, y + h), (0, 255, 255), 2)      
            #     text = labels[i]
            #     cv2.putText(self.frame, text, (x + 2, y + 20), cv2.FONT_HERSHEY_SIMPLEX,0.6, (0, 200, 255), 2)

            print(labels)
            self.blobs, current_blob_id = add_new_blobs(boxes, labels, self.blobs, self.frame, self.tracker, self.blob_id, self.counting_line, self.cl_position, self.mcdf, self.direction)
            self.blob_id = current_blob_id
            self.blobs = remove_duplicates(self.blobs)
            self.frame_count = 0

        self.frame_count += 1

        return log

    def visualize(self):
        frame = self.frame

        # draw and label blob bounding boxes
        counter = 0

        for _id, (blob, _label) in self.blobs.items():
            (x, y, w, h) = [int(v) for v in blob.bounding_box]
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            # if counter < len(self.labels):
            #     text = self.labels[counter]
            #     counter += 1
            # else:
            #     text = "No Label"
            # cv2.putText(self.frame, text, (x + 2, y + 20), cv2.FONT_HERSHEY_SIMPLEX,0.6, (0, 200, 255), 2)  
            # cv2.putText(frame, 'v_' + str(_id), (x, y - 2), cv2.FONT_HERSHEY_DUPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
            cv2.putText(frame, 'v_' + str(_id) +" "+ str(_label), (x, y - 2), cv2.FONT_HERSHEY_DUPLEX, 1, (0, 255, 0), 2, cv2.LINE_AA)
            # text = "{}: {:.4f}".format(result[0]['brand'], float(result[0]['prob']))
            # cv2.putText(image, text, (x + 2, y + 20), cv2.FONT_HERSHEY_SIMPLEX,0.6, color, 2)

        # draw counting line

        # draw counting line
        if self.counting_line != None:
            cv2.line(frame, self.counting_line[0], self.counting_line[1], (0, 255, 0), 3)
        # display vehicle count
        cv2.putText(frame, 'Count: ' + str(self.vehicle_count), (20, 60), cv2.FONT_HERSHEY_DUPLEX, 2, (255, 0, 0), 2, cv2.LINE_AA)
        # show detection roi
        if self.show_droi:
            frame = draw_roi(frame, self.droi)

        return frame



if __name__ == '__main__':
    # parse CLI arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('video', help='relative/absolute path to video or camera input of traffic scene')
    parser.add_argument('--iscam', action='store_true', help='specify if video capture is from a camera')
    parser.add_argument('--droi', help='specify a detection region of interest (ROI) \
                        i.e a set of vertices that represent the area (polygon) \
                        where you want detections to be made (format: 1,2|3,4|5,6|7,8|9,10 \
                        default: 0,0|frame_width,0|frame_width,frame_height|0,frame_height \
                        [i.e the whole video frame])')
    parser.add_argument('--showdroi', action='store_true', help='display/overlay the detection roi on the video')
    parser.add_argument('--mcdf', type=int, help='maximum consecutive detection failures \
                        i.e number of detection failures before it\'s concluded that \
                        an object is no longer in the frame')
    parser.add_argument('--mctf', type=int, help='maximum consecutive tracking failures \
                        i.e number of tracking failures before the tracker concludes \
                        the tracked object has left the frame')
    parser.add_argument('--di', type=int, help='detection interval i.e number of frames \
                        before detection is carried out again (in order to find new vehicles \
                        and update the trackers of old ones)')
    parser.add_argument('--detector', help='select a model/algorithm to use for vehicle detection \
                        (options: yolo, haarc, bgsub, ssd, tfoda | default: yolo)')
    parser.add_argument('--tracker', help='select a model/algorithm to use for vehicle tracking \
                        (options: csrt, kcf, camshift | default: kcf)')
    parser.add_argument('--record', action='store_true', help='record video and vehicle count logs')
    parser.add_argument('--headless', action='store_true', help='run VCS without UI display')
    parser.add_argument('--clposition', help='position of counting line (options: top, bottom, \
                        left, right | default: bottom)')
    parser.add_argument('--output', help='name of output')
    parser.add_argument('--framerate', type=int, help='Frame rate of the video')
    parser.add_argument('--direction', type=int, help='Direction of motion if towards bottom ignore else 1')
    args = parser.parse_args()

    start = time.time()


    temp1 = start
    

    # capture traffic scene video
    video = int(args.video) if args.iscam else args.video
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        sys.exit('Error capturing video.')
    ret, frame = cap.read()





# ROI SELECTOR 
    # if ret:
    #     cv2.imwrite("temp.jpg", frame)
#     temp = selectroi("temp.jpg")
# #    print(roi[0])
#     roi = temp[0]
#     line = temp[1]
    # print(roi)
    # cv2.destroyAllWindows()
    # os.remove("temp.jpg")

  #   f_height, f_width, _ = frame.shape

  #   di = 10 if args.di == None else args.di
  #   mcdf = 2 if args.mcdf == None else args.mcdf
  #   mctf = 3 if args.mctf == None else args.mctf
  #   detector = 'yolo' if args.detector == None else args.detector
  #   tracker = 'kcf' if args.tracker == None else args.tracker
  #   # create detection region of interest polygon
  #   if args.droi == None:
        # droi = [roi]

  #   else:
  #       tmp_droi = []
  #       points = args.droi.replace(' ', '').split('|')
  #       for point_str in points:
  #           point = tuple(map(int, point_str.split(',')))
  #           tmp_droi.append(point)
  #       droi = tmp_droi




    f_height, f_width, _ = frame.shape

    di = 10 if args.di == None else args.di
    mcdf = 2 if args.mcdf == None else args.mcdf
    mctf = 3 if args.mctf == None else args.mctf
    detector = 'yolo' if args.detector == None else args.detector
    tracker = 'kcf' if args.tracker == None else args.tracker
    # create detection region of interest polygon
    if args.droi == None:
        droi = [(0, 0), (f_width, 0), (f_width, f_height), (0, f_height)]
    else:
        tmp_droi = []
        points = args.droi.replace(' ', '').split('|')
        for point_str in points:
            point = tuple(map(int, point_str.split(',')))
            tmp_droi.append(point)
        droi = tmp_droi

    vehicle_counter = VehicleCounter(frame, detector, tracker, droi, args.showdroi, mcdf, mctf, di, args.clposition, args.framerate)

    if args.record:
        # initialize video object and log file to record counting
        # output_video_path='./videos/output.avi'
        output_video_path = "./output/" + args.output + ".avi"
        output_video = cv2.VideoWriter(output_video_path, \
                                            cv2.VideoWriter_fourcc('M','J','P','G'), \
                                            30, \
                                            (f_width, f_height))
        log_file_name='log.txt'
        with contextlib.suppress(FileNotFoundError):
            os.remove(log_file_name)
        log_file = open(log_file_name, 'a')
        log_file.write('vehicle_id, count, datetime\n')
        log_file.flush()

    # main loop
    print('VCS running...')
    while args.iscam or cap.get(cv2.CAP_PROP_POS_FRAMES) + 1 < cap.get(cv2.CAP_PROP_FRAME_COUNT):
        if ret:
            log = vehicle_counter.count(frame)
            output_frame = vehicle_counter.visualize()

            if args.record:
                output_video.write(output_frame)
                for item in log:
                    _row = '{0}, {1}, {2}\n'.format('v_' + str(item['blob_id']), item['count'], item['datetime'])
                    log_file.write(_row)
                    log_file.flush()

            if not args.headless:
                resized_frame = cv2.resize(output_frame, (858, 480))
                cv2.imshow('tracking', resized_frame)

        k = cv2.waitKey(1) & 0xFF
        # save frame if 's' key is pressed
        if k & 0xFF == ord('s'):
            cv2.imwrite(os.path.join('screenshots', 'ss_' + uuid.uuid4().hex + '.png'), vc_frame)
            print('Screenshot taken.')
        # end video loop if 'q' key is pressed
        if k & 0xFF == ord('q'):
            print('Video exited.')
            break
        
        ret, frame = cap.read()
        vehicle_counter.frameno +=1

        if (time.time() - temp1 > 5):
        	print(vehicle_counter.count_list)
        	print("TOTAL COUNT", vehicle_counter.vehicle_count)
        	temp1 = time.time()
        	print("Frame", vehicle_counter.frameno)

    # end capture, close window, close log file and video object if any
    cap.release()
    if not args.headless:
        cv2.destroyAllWindows()
    if args.record:
        log_file.close()
        output_video.release()
    print('End of video.')
    end = time.time()
    print("[INFO] PROGRAM TOOK {:.6f} seconds".format(end - start))

    df = pd.DataFrame(vehicle_counter.count_list)
    df.to_csv("out.csv", index=None)
    print(df)
